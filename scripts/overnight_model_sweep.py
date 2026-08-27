#!/usr/bin/env python3
"""Overnight Model Sweep Runner for Llama, Partner Model Garden, and OpenModels.

Automates sequential model deployment, SOC Tier 1 evaluation, and cleanup
with $0 idle cost guarantees.
"""

import argparse
import datetime
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("GOOGLE_API_USE_CLIENT_CERTIFICATE", "false")

ROOT_DIR = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT_DIR / "configs" / "models.json"
RESULTS_DIR = ROOT_DIR / "docs" / "soc_eval_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(ROOT_DIR / "overnight_sweep.log", mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger("PartnerModelSweep")

# Target new models queue
NEW_MODELS_QUEUE = [
    # Front of Queue (Flash Next, MoE, GLM, DeepSeek & Kimi variants)
    "qwen3.8-flash-next",
    "qwen3.8-flash-next-fp8",
    "qwen3.8-2.4t-a95b-fp8",
    "glm-5.3-flash",
    "deepseek-v4-pro",
    "kimi-k3",
    # Recommended Additional Llamas (End of Queue)
    "llama-3.1-405b-instruct-maas",
    "llama-3.2-11b-vision-instruct-maas",
    "llama-3.2-3b-instruct",
    "llama-guard-3-8b",
    "llama-3.1-nemotron-70b-instruct",
]


def load_catalog():
    if CATALOG_PATH.exists():
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def run_cmd(cmd, check=True, capture=True):
    logger.info(f"Executing: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    if isinstance(cmd, str):
        res = subprocess.run(cmd, shell=True, text=True, capture_output=capture)
    else:
        res = subprocess.run(cmd, text=True, capture_output=capture)
    if check and res.returncode != 0:
        logger.error(f"Command failed (code {res.returncode}):\n{res.stderr}")
        raise RuntimeError(f"Command failed: {res.stderr}")
    return res


def evaluate_maas_model(flavor: str):
    logger.info(f">>> Evaluating MaaS model: {flavor}")
    output_report = RESULTS_DIR / f"{flavor}_report.md"
    cmd = [
        "uv",
        "run",
        "python3",
        "-m",
        "scripts.eval_soc_agent",
        "--flavor",
        flavor,
        "--output-report",
        str(output_report),
    ]
    res = run_cmd(cmd, check=False, capture=False)
    return res.returncode == 0


def deploy_and_eval_dedicated_model(flavor: str, spec: dict, project_id: str, region: str):
    logger.info(f">>> Processing Dedicated Model Garden / OpenModel: {flavor}")
    compute = spec.get("compute", {})
    machine_type = compute.get("machineType", "g2-standard-48")
    raw_accel = compute.get("acceleratorType", "NVIDIA_L4")
    if "l4" in raw_accel.lower():
        accelerator_type = "NVIDIA_L4"
    elif "a100" in raw_accel.lower():
        accelerator_type = "NVIDIA_TESLA_A100"
    elif "6000" in raw_accel.lower() or "rtx" in raw_accel.lower():
        accelerator_type = "NVIDIA_RTX_PRO_6000"
    else:
        accelerator_type = raw_accel
    accelerator_count = compute.get("acceleratorCount", 4)
    runtime = spec.get("runtime", {})
    container_image = runtime.get(
        "containerImage",
        "us-docker.pkg.dev/vertex-ai/vertex-vision-model-garden-dockers/pytorch-vllm-serve:20250312_0916_RC01",
    )
    model_type = spec.get("type", "model_garden")
    open_model_id = spec.get("openModelId")

    endpoint_id = None
    try:
        if model_type == "open_model" and open_model_id:
            logger.info(f"Deploying OpenModel {open_model_id}...")
            import vertexai
            from vertexai import model_garden

            vertexai.init(project=project_id, location=region)
            model = model_garden.OpenModel(open_model_id)
            timestamp = int(time.time() * 1000)
            safe_flavor = flavor.replace("-", "_").replace(".", "_")

            endpoint = model.deploy(
                accept_eula=True,
                machine_type=machine_type,
                accelerator_type=accelerator_type,
                accelerator_count=accelerator_count,
                serving_container_image_uri=container_image,
                endpoint_display_name=f"{safe_flavor}-sweep-endpoint",
                model_display_name=f"{safe_flavor}-{timestamp}",
                use_dedicated_endpoint=True,
                reservation_affinity_type="NO_RESERVATION",
            )
            endpoint_id = endpoint.resource_name.split("/")[-1]
        else:
            logger.info(f"Deploying Model Garden flavor via scripts/vertex_deploy.sh: {flavor}...")
            run_cmd([str(ROOT_DIR / "scripts" / "vertex_deploy.sh"), flavor])
            # Find active endpoint ID
            list_res = run_cmd([
                "gcloud",
                "ai",
                "endpoints",
                "list",
                f"--region={region}",
                f"--project={project_id}",
                "--format=json",
            ])
            endpoints = json.loads(list_res.stdout)
            for ep in endpoints:
                if flavor in ep.get("displayName", ""):
                    endpoint_id = ep["name"].split("/")[-1]
                    break

        if not endpoint_id:
            logger.error(f"Failed to find endpoint ID for {flavor}")
            return False

        logger.info(f"Endpoint active: {endpoint_id}. Starting SOC evaluation...")
        output_report = RESULTS_DIR / f"{flavor}_report.md"
        eval_cmd = [
            "uv",
            "run",
            "python3",
            "-m",
            "scripts.eval_soc_agent",
            "--flavor",
            flavor,
            "--endpoint-id",
            endpoint_id,
            "--output-report",
            str(output_report),
        ]
        eval_res = run_cmd(eval_cmd, check=False, capture=False)
        return eval_res.returncode == 0

    finally:
        if endpoint_id:
            logger.info(f">>> Cleaning up endpoint {endpoint_id} to ensure $0.00 idle cost...")
            run_cmd([str(ROOT_DIR / "scripts" / "vertex_undeploy.sh")], check=False)
            run_cmd(
                [
                    "gcloud",
                    "ai",
                    "endpoints",
                    "delete",
                    endpoint_id,
                    f"--region={region}",
                    f"--project={project_id}",
                    "--quiet",
                ],
                check=False,
            )


def generate_summary_table():
    logger.info(">>> Generating comprehensive comparative summary table...")
    results = []
    for json_file in RESULTS_DIR.glob("*_report.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                flavor = data.get("flavor") or data.get("model_flavor") or json_file.stem.replace("_report", "")
                summary = data.get("summary", {})
                pass_rate = summary.get("pass_rate", data.get("pass_rate", 0.0))
                avg_score = summary.get("avg_rubric_score", data.get("average_score", 0.0))
                avg_lat = summary.get("avg_latency_s", data.get("average_latency_sec", 0.0))
                gen_tps = summary.get("avg_generation_tps", data.get("output_tps", 0.0))
                tot_tps = summary.get("avg_total_tps", data.get("total_tps", 0.0))
                tools = summary.get("total_tool_calls", data.get("total_tool_calls", 0))

                results.append({
                    "flavor": flavor,
                    "pass_rate": f"{pass_rate:.1f}%" if isinstance(pass_rate, (int, float)) else str(pass_rate),
                    "avg_score": f"{avg_score:.1f}" if isinstance(avg_score, (int, float)) else str(avg_score),
                    "avg_latency": f"{avg_lat:.2f}s" if isinstance(avg_lat, (int, float)) else str(avg_lat),
                    "output_tps": f"{gen_tps:.2f}" if isinstance(gen_tps, (int, float)) else str(gen_tps),
                    "total_tps": f"{tot_tps:.2f}" if isinstance(tot_tps, (int, float)) else str(tot_tps),
                    "tool_calls": tools,
                })
        except Exception as e:
            logger.warning(f"Failed to read {json_file}: {e}")

    try:
        results.sort(key=lambda x: float(x["avg_score"].replace("/100", "").strip()), reverse=True)
    except Exception:
        pass

    summary_md = RESULTS_DIR / "OVERNIGHT_SWEEP_SUMMARY.md"
    with open(summary_md, "w", encoding="utf-8") as f:
        f.write("# Partner & New Models Sweep Benchmark Summary\n\n")
        f.write(f"Generated at: {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n\n")
        f.write("| Model Flavor | Pass Rate | Avg Rubric | Latency | Output TPS | Total TPS | Tool Calls |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for r in results:
            f.write(
                f"| **{r['flavor']}** | {r['pass_rate']} | {r['avg_score']} / 100 | {r['avg_latency']} | {r['output_tps']} tok/s | {r['total_tps']} tok/s | {r['tool_calls']} |\n"
            )

    logger.info(f"Saved master summary to {summary_md}")


def main():
    parser = argparse.ArgumentParser(description="Run Sweep across new partner & OpenModels.")
    parser.add_argument("--project-id", default=os.environ.get("GCP_PROJECT_ID", "dandye-0324-chronicle"))
    parser.add_argument("--region", default=os.environ.get("GCP_REGION", "us-central1"))
    parser.add_argument("--models", nargs="*", help="List of model flavors to evaluate in sequence")
    args = parser.parse_args()

    catalog = load_catalog()

    # Target exclusively the new models
    sweep_models = args.models or NEW_MODELS_QUEUE

    logger.info("==================================================================")
    logger.info(" Starting New & Partner Model Sweep")
    logger.info(f" Total Models in Queue: {len(sweep_models)}")
    logger.info(f" Models: {', '.join(sweep_models)}")
    logger.info("==================================================================")

    for idx, flavor in enumerate(sweep_models, 1):
        logger.info(f"\n==================================================================")
        logger.info(f" [{idx}/{len(sweep_models)}] Starting Sweep for: {flavor}")
        logger.info(f"==================================================================")

        spec = catalog.get(flavor, {})
        target = spec.get("supportedTargets", [])
        model_type = spec.get("type", "")

        try:
            if "vertex_maas" in target or model_type == "maas" or "gemini" in flavor:
                evaluate_maas_model(flavor)
            else:
                deploy_and_eval_dedicated_model(flavor, spec, args.project_id, args.region)
        except Exception as e:
            logger.error(f"Error evaluating {flavor}: {e}", exc_info=True)

        generate_summary_table()

    logger.info("\n==================================================================")
    logger.info(" New & Partner Model Sweep Finished Successfully!")
    logger.info("==================================================================")


if __name__ == "__main__":
    main()
