"""Execute a pinned serving configuration; Docker observations are not model attestation."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.experiment_run import write_json
from scripts.serving_config import load_serving_config, serving_config_hash, validate_serving_config

SERVER = "vllm-server"
EVALUATOR = "soc-evaluator"
SCOPE = "container_image_ids_and_requested_model_revision"
IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")
FORWARDED_ENV = (
    "EXPERIMENT_RUN_ID", "EXPERIMENT_CONFIGURATION_HASH", "EXPERIMENT_SOURCE_VERIFIED",
    "EXPERIMENT_SOURCE_BUNDLE_SHA256", "EXPERIMENT_SOURCE_COMMIT",
    "GOOGLE_CLOUD_PROJECT", "GCP_PROJECT_ID", "GOOGLE_CLOUD_LOCATION",
)


def docker(*args, capture=False, timeout=60, check=True):
    return subprocess.run(["docker", *args], check=check, text=True,
                          capture_output=capture, timeout=timeout)


def image_id(reference):
    data = json.loads(docker("image", "inspect", reference, capture=True).stdout)
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        raise ValueError("Invalid Docker image inspection")
    info = data[0]
    identity = info.get("Id")
    digests = info.get("RepoDigests")
    digest = reference.rsplit("@", 1)[1]
    if (not isinstance(identity, str) or not IMAGE_ID.fullmatch(identity)
            or not isinstance(digests, list)
            or not any(isinstance(item, str) and item.endswith("@" + digest) for item in digests)):
        raise ValueError("Docker image does not match requested digest")
    return identity


def check_container(name, expected):
    observed = docker("inspect", "--format", "{{.Image}}", name, capture=True).stdout.strip()
    if observed != expected:
        raise ValueError("Container image ID mismatch")


def check_server_running():
    if docker("inspect", "--format", "{{.State.Running}}", SERVER, capture=True).stdout.strip() != "true":
        raise ValueError("Pinned server is not running")


def start_server(config, cache: Path, evidence_path: Path):
    validate_serving_config(config)
    evidence_path.unlink(missing_ok=True)
    ids = {}
    for kind in ("serving", "evaluator"):
        reference = config[f"{kind}_image"]
        docker("pull", "--platform", "linux/amd64", reference, timeout=900)
        ids[f"{kind}_image_id"] = image_id(reference)
    params = config["parameters"]
    command = ["create", "--platform", "linux/amd64", "--name", SERVER,
               "--gpus", "all", "--ipc=host", "--network=host",
               "--mount", f"type=bind,src={cache.resolve()},dst=/root/.cache/huggingface",
               "--entrypoint", "python3"]
    if os.environ.get("HF_TOKEN"):
        command += ["--env", "HF_TOKEN"]
    command += [config["serving_image"], "-m", "vllm.entrypoints.openai.api_server",
                "--model", config["model_repository"],
                "--revision", config["model_revision"],
                "--tokenizer-revision", config["model_revision"],
                "--code-revision", config["model_revision"],
                "--tensor-parallel-size", str(params["tensor_parallel_size"]),
                "--max-model-len", str(params["max_model_len"]),
                "--gpu-memory-utilization", str(params["gpu_memory_utilization"]),
                "--host", "0.0.0.0", "--port", "8080", "--trust-remote-code"]
    docker(*command)
    check_container(SERVER, ids["serving_image_id"])
    docker("start", SERVER)
    check_server_running()
    evidence = {"status": "SERVER_STARTED", "scope": SCOPE, "configuration": config,
                "configuration_hash": serving_config_hash(config), **ids}
    write_json(evidence_path, evidence)
    return evidence


def run_evaluator(config, source: Path, output: Path, evidence_path: Path):
    validate_serving_config(config)
    evidence = json.loads(evidence_path.read_text())
    if (not isinstance(evidence, dict) or evidence.get("status") != "SERVER_STARTED" or evidence.get("configuration") != config
            or evidence.get("configuration_hash") != serving_config_hash(config)):
        raise ValueError("Missing or conflicting server startup evidence")
    for kind in ("serving", "evaluator"):
        if image_id(config[f"{kind}_image"]) != evidence.get(f"{kind}_image_id"):
            raise ValueError("Pinned image changed after startup")
    check_container(SERVER, evidence["serving_image_id"])
    check_server_running()
    evidence["status"] = "PINNED_IMAGES_VERIFIED"
    command = ["create", "--platform", "linux/amd64", "--name", EVALUATOR,
               "--network=host", "--user", "0:0", "--workdir", "/workspace", "--entrypoint", "python3",
               "--mount", f"type=bind,src={source.resolve()},dst=/workspace,readonly",
               "--mount", f"type=bind,src={output.resolve()},dst=/output",
               "--env", "PYTHONDONTWRITEBYTECODE=1",
               "--env", "EXPERIMENT_SERVING_RUNTIME=" + json.dumps(evidence, separators=(",", ":"))]
    for name in FORWARDED_ENV:
        if name in os.environ:
            command += ["--env", name]
    flavor = config["target_flavor"]
    command += [config["evaluator_image"], "-I", "/workspace/scripts/eval_soc_agent.py",
                "--flavor", flavor, "--cloudrun-url", "http://127.0.0.1:8080",
                "--output-report", f"/output/soc_tier1_eval_report_{flavor}.md",
                "--output-json", f"/output/soc_tier1_eval_results_{flavor}.json"]
    created = False
    try:
        docker(*command)
        created = True
        check_container(EVALUATOR, evidence["evaluator_image_id"])
        # The environment is supplied on create but no evaluator runs before inspection.
        write_json(evidence_path, evidence)
        attached = docker("start", "--attach", EVALUATOR, timeout=3600, check=False)
        state = json.loads(docker("inspect", "--format", "{{json .State}}", EVALUATOR, capture=True).stdout)
        if not isinstance(state, dict):
            raise ValueError("Evaluator state unavailable")
        code = state.get("ExitCode")
        if (state.get("Running") is not False or state.get("Status") != "exited"
                or state.get("Error") or type(code) is not int or not 0 <= code <= 255
                or (attached.returncode != 0 and code == 0)):
            raise ValueError("Evaluator exit status unavailable")
        return code
    finally:
        if created:
            docker("rm", "--force", EVALUATOR)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("validate", "start", "evaluate"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--flavor", required=True)
    parser.add_argument("--model-repository", required=True)
    parser.add_argument("--tp-size", type=int, required=True)
    parser.add_argument("--extra-flags", default="")
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        config = load_serving_config(args.config)
        if serving_config_hash(config) != args.sha256:
            raise ValueError("Serving configuration hash mismatch")
        validate_serving_config(config, {"flavor": args.flavor, "hf_repo": args.model_repository,
                                        "tensor_parallel_size": args.tp_size,
                                        "extra_vllm_flags": args.extra_flags})
        if args.action == "validate":
            return 0
        from scripts.evaluation_provenance import _launch_identity, _verified_source_bundle
        if _launch_identity()[0] is None or _verified_source_bundle() is None:
            raise ValueError("Pinned runtime requires launch and verified source identities")
        if args.action == "start":
            if args.cache is None:
                raise ValueError("Cache directory required")
            start_server(config, args.cache, args.evidence)
            return 0
        if args.source_root is None or args.output_dir is None:
            raise ValueError("Source and output directories required")
        return run_evaluator(config, args.source_root, args.output_dir, args.evidence)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        write_json(args.evidence, {"status": "FAILED", "error_type": type(exc).__name__})
        print(f"[ERROR] Pinned runtime failed: {type(exc).__name__}", file=sys.stderr)
        return 78


if __name__ == "__main__":
    raise SystemExit(main())
