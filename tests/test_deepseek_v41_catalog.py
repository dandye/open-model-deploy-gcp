"""Hermetic unit tests for DeepSeek-V4.1-Flash catalog entries, deploy script, and shell helpers."""

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts import deploy_open_model as deploy_mod

CATALOG_PATH = ROOT_DIR / "configs" / "models.json"
EXPECTED_EXTRA_ARGS = [
    "--trust-remote-code",
    "--kv-cache-dtype=fp8",
    "--enable-expert-parallel",
    "--engram-config.cpu_offload=True",
    "--tool-call-parser=deepseek_v41",
    "--reasoning-parser=deepseek_v41",
    "--enable-auto-tool-choice",
    "--max-num-seqs=128",
    "--mm-encoder-tp-mode=data",
]
EXPECTED_DSPARK_ARGS = [
    "--speculative_config.method=dspark",
    "--speculative_config.num_speculative_tokens=5",
]


class TestDeepSeekV41Catalog(unittest.TestCase):
    """Validate DeepSeek-V4.1-Flash entries in configs/models.json."""

    @classmethod
    def setUpClass(cls):
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            cls.catalog = json.load(f)

    def test_primary_maas_1017_entry(self):
        key = "deepseek-v4.1-flash-1017-maas"
        self.assertIn(key, self.catalog)
        entry = self.catalog[key]

        self.assertEqual(entry["displayName"], "DeepSeek V4.1 Flash 1017 (Vertex MaaS)")
        self.assertEqual(entry["family"], "deepseek-v4.1")
        self.assertEqual(entry["provider"], "deepseek-ai")
        self.assertEqual(entry["type"], "maas")
        self.assertEqual(entry["maasModelId"], "deepseek-ai/deepseek-v4.1-flash-1017-maas")
        self.assertEqual(entry["modelId"], "deepseek-ai/deepseek-v4.1-flash-1017-maas")
        self.assertEqual(entry["region"], "global")
        self.assertEqual(entry["modalities"], ["text", "image"])
        self.assertEqual(
            entry["params"],
            "552B CED Multimodal MoE (8B prefill / 16B decode active, CSA2 FP4 KV, 1M context)",
        )
        self.assertEqual(entry["hfRepo"], "deepseek-ai/DeepSeek-V4.1-Flash-1017")
        self.assertEqual(entry["hourlyCostUsd"], 0.0)
        self.assertEqual(entry["supportedTargets"], ["vertex_maas"])
        self.assertNotIn("compute", entry)

    def test_baseline_maas_entry(self):
        key = "deepseek-v4.1-flash-maas"
        self.assertIn(key, self.catalog)
        entry = self.catalog[key]

        self.assertEqual(entry["displayName"], "DeepSeek V4.1 Flash (Vertex MaaS)")
        self.assertEqual(entry["family"], "deepseek-v4.1")
        self.assertEqual(entry["provider"], "deepseek-ai")
        self.assertEqual(entry["type"], "maas")
        self.assertEqual(entry["maasModelId"], "deepseek-ai/deepseek-v4.1-flash-maas")
        self.assertEqual(entry["modelId"], "deepseek-ai/deepseek-v4.1-flash-maas")
        self.assertEqual(entry["region"], "global")
        self.assertEqual(entry["modalities"], ["text", "image"])
        self.assertEqual(
            entry["params"],
            "552B CED Multimodal MoE (8B prefill / 16B decode active, CSA2 FP4 KV, 1M context)",
        )
        self.assertEqual(entry["hfRepo"], "deepseek-ai/DeepSeek-V4.1-Flash")
        self.assertEqual(entry["hourlyCostUsd"], 0.0)
        self.assertEqual(entry["supportedTargets"], ["vertex_maas"])
        self.assertNotIn("compute", entry)

    def test_curated_model_garden_1017_entry(self):
        key = "deepseek-v4.1-flash-1017"
        self.assertIn(key, self.catalog)
        entry = self.catalog[key]

        self.assertEqual(entry["displayName"], "DeepSeek V4.1 Flash 1017 (Model Garden)")
        self.assertEqual(entry["family"], "deepseek-v4.1")
        self.assertEqual(entry["provider"], "deepseek-ai")
        self.assertEqual(entry["type"], "open_model")
        self.assertEqual(entry["modalities"], ["text", "image"])
        self.assertEqual(
            entry["params"],
            "552B CED Multimodal MoE (8B prefill / 16B decode active, CSA2 FP4 KV, 1M context)",
        )
        self.assertEqual(entry["publisherModel"], "publishers/deepseek-ai/models/deepseek-v4.1")
        self.assertEqual(
            entry["openModelId"],
            "publishers/deepseek-ai/models/deepseek-v4.1@deepseek-v4.1-flash-1017",
        )
        self.assertEqual(entry["version"], "deepseek-v4.1-flash-1017")
        self.assertEqual(entry["hfRepo"], "deepseek-ai/DeepSeek-V4.1-Flash-1017")
        self.assertEqual(entry["supportedTargets"], ["vertex", "vertex_open_model"])

        compute = entry["compute"]
        self.assertEqual(compute["machineType"], "a3-megagpu-8g")
        self.assertEqual(compute["acceleratorType"], "NVIDIA_H100_MEGA_80GB")
        self.assertEqual(compute["acceleratorCount"], 8)
        self.assertEqual(compute["hostRamGb"], 1872)
        self.assertEqual(compute["hourlyCostUsd"], 88.49)

        alternatives = compute["validatedAlternatives"]
        self.assertIsInstance(alternatives, list)
        self.assertGreaterEqual(len(alternatives), 2)
        by_machine = {alt["machineType"]: alt for alt in alternatives}
        self.assertIn("a3-ultragpu-8g", by_machine)
        self.assertEqual(by_machine["a3-ultragpu-8g"]["acceleratorType"], "NVIDIA_H200_141GB")
        self.assertEqual(by_machine["a3-ultragpu-8g"]["acceleratorCount"], 8)
        self.assertEqual(by_machine["a3-ultragpu-8g"]["speculativeDecoding"], "dspark")
        self.assertEqual(by_machine["a3-ultragpu-8g"]["numSpeculativeTokens"], 5)

        self.assertIn("a4-highgpu-8g", by_machine)
        self.assertEqual(by_machine["a4-highgpu-8g"]["acceleratorType"], "NVIDIA_B200")
        self.assertEqual(by_machine["a4-highgpu-8g"]["acceleratorCount"], 8)
        self.assertEqual(by_machine["a4-highgpu-8g"]["speculativeDecoding"], "dspark")
        self.assertEqual(by_machine["a4-highgpu-8g"]["numSpeculativeTokens"], 5)
        self.assertEqual(by_machine["a4-highgpu-8g"]["speculativeArgs"], EXPECTED_DSPARK_ARGS)

        runtime = entry["runtime"]
        self.assertEqual(
            runtime["containerImage"],
            "us-docker.pkg.dev/agent-platform-mg-public/containers/pytorch-vllm-serve:model-garden.pytorch-vllm-serve-release_20260922.00_p0",
        )
        self.assertEqual(runtime["containerPort"], 7080)
        self.assertEqual(runtime["predictRoute"], "/generate")
        self.assertEqual(runtime["healthRoute"], "/ping")
        self.assertEqual(runtime["tensorParallelSize"], 8)
        self.assertEqual(runtime["swapSpaceGb"], 0)
        self.assertEqual(runtime["sharedMemorySizeMb"], 40960)
        self.assertEqual(runtime["deploymentTimeoutSeconds"], 7200)
        self.assertEqual(runtime["gpuMemoryUtilization"], 0.90)
        self.assertEqual(runtime["maxModelLen"], 1048576)
        self.assertEqual(runtime["extraArgs"], EXPECTED_EXTRA_ARGS)
        self.assertEqual(runtime["speculativeArgsDspark"], EXPECTED_DSPARK_ARGS)


class TestDeployOpenModelDeepSeekV41(unittest.TestCase):
    """Validate hermetic dry-run, SDK kwargs, and serverless MaaS guardrails."""

    def test_dry_run_prints_shared_memory_and_timeout_banner(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = deploy_mod.deploy_open_model(
                flavor="deepseek-v4.1-flash-1017",
                dry_run=True,
            )
        self.assertIsNone(result)
        output = buf.getvalue()
        self.assertIn(
            "publishers/deepseek-ai/models/deepseek-v4.1@deepseek-v4.1-flash-1017",
            output,
        )
        self.assertIn("a3-megagpu-8g", output)
        self.assertIn("8x NVIDIA_H100_MEGA_80GB", output)
        self.assertIn("Shared Memory:      40960 MB", output)
        self.assertIn("Deployment Timeout: 7200s", output)
        self.assertIn("[DRY RUN] Skipping actual deployment.", output)

    def test_mocked_sdk_deploy_preserves_publishers_container_spec(self):
        fake_endpoint = mock.MagicMock()
        fake_endpoint.resource_name = "projects/test-proj/locations/us-central1/endpoints/12345"
        fake_open_model_instance = mock.MagicMock()
        fake_open_model_instance.deploy.return_value = fake_endpoint

        fake_model_garden = types.ModuleType("vertexai.model_garden")
        fake_model_garden.OpenModel = mock.MagicMock(return_value=fake_open_model_instance)
        fake_vertexai = types.ModuleType("vertexai")
        fake_vertexai.init = mock.MagicMock()
        fake_vertexai.model_garden = fake_model_garden

        with mock.patch.dict(
            sys.modules,
            {"vertexai": fake_vertexai, "vertexai.model_garden": fake_model_garden},
        ):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                endpoint = deploy_mod.deploy_open_model(
                    flavor="deepseek-v4.1-flash-1017",
                    project_id="test-proj",
                    location="us-central1",
                    dry_run=False,
                )

        self.assertIs(endpoint, fake_endpoint)
        fake_vertexai.init.assert_called_once_with(project="test-proj", location="us-central1")
        fake_model_garden.OpenModel.assert_called_once_with(
            "publishers/deepseek-ai/models/deepseek-v4.1@deepseek-v4.1-flash-1017"
        )

        deploy_kwargs = fake_open_model_instance.deploy.call_args.kwargs
        self.assertEqual(deploy_kwargs["machine_type"], "a3-megagpu-8g")
        self.assertEqual(deploy_kwargs["accelerator_type"], "NVIDIA_H100_MEGA_80GB")
        self.assertEqual(deploy_kwargs["accelerator_count"], 8)
        self.assertIsInstance(deploy_kwargs["deploy_request_timeout"], float)
        self.assertEqual(deploy_kwargs["deploy_request_timeout"], 7200.0)
        self.assertEqual(deploy_kwargs["serving_container_deployment_timeout"], 7200)
        self.assertNotIn("serving_container_image_uri", deploy_kwargs)
        self.assertNotIn("serving_container_shared_memory_size_mb", deploy_kwargs)

    def test_mocked_sdk_deploy_non_publisher_passes_image_and_shared_memory(self):
        fake_endpoint = mock.MagicMock()
        fake_endpoint.resource_name = "projects/test-proj/locations/us-central1/endpoints/67890"
        fake_open_model_instance = mock.MagicMock()
        fake_open_model_instance.deploy.return_value = fake_endpoint

        fake_model_garden = types.ModuleType("vertexai.model_garden")
        fake_model_garden.OpenModel = mock.MagicMock(return_value=fake_open_model_instance)
        fake_vertexai = types.ModuleType("vertexai")
        fake_vertexai.init = mock.MagicMock()
        fake_vertexai.model_garden = fake_model_garden

        with mock.patch.dict(
            sys.modules,
            {"vertexai": fake_vertexai, "vertexai.model_garden": fake_model_garden},
        ):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                deploy_mod.deploy_open_model(
                    flavor="qwen3.8-27b",
                    project_id="test-proj",
                    location="us-central1",
                    deployment_timeout=5400,
                    shared_memory_size_mb=40960,
                    dry_run=False,
                )

        deploy_kwargs = fake_open_model_instance.deploy.call_args.kwargs
        self.assertIn("serving_container_image_uri", deploy_kwargs)
        self.assertEqual(deploy_kwargs["serving_container_shared_memory_size_mb"], 40960)
        self.assertEqual(deploy_kwargs["deploy_request_timeout"], 5400.0)
        self.assertEqual(deploy_kwargs["serving_container_deployment_timeout"], 5400)

    def test_maas_flavors_rejected_in_python_api(self):
        for maas_flavor, expected_id in [
            ("deepseek-v4.1-flash-1017-maas", "deepseek-ai/deepseek-v4.1-flash-1017-maas"),
            ("deepseek-v4.1-flash-maas", "deepseek-ai/deepseek-v4.1-flash-maas"),
        ]:
            for dry_run_flag in (True, False):
                with self.assertRaises(ValueError) as ctx:
                    deploy_mod.deploy_open_model(flavor=maas_flavor, dry_run=dry_run_flag)
                msg = str(ctx.exception)
                self.assertIn(expected_id, msg)
                self.assertIn("global", msg)
                self.assertIn("scripts/benchmark.py", msg)
                self.assertIn("scripts/eval_soc_agent.py", msg)

    def test_cli_dry_run_and_maas_rejection_exit_codes(self):
        ok_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT_DIR / "scripts" / "deploy_open_model.py"),
                "--flavor",
                "deepseek-v4.1-flash-1017",
                "--deployment-timeout",
                "7200",
                "--dry-run",
            ],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(ok_proc.returncode, 0, msg=ok_proc.stderr)
        self.assertIn("Shared Memory:      40960 MB", ok_proc.stdout)
        self.assertIn("Deployment Timeout: 7200s", ok_proc.stdout)

        for maas_flavor in ("deepseek-v4.1-flash-1017-maas", "deepseek-v4.1-flash-maas"):
            err_proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT_DIR / "scripts" / "deploy_open_model.py"),
                    "--flavor",
                    maas_flavor,
                    "--dry-run",
                ],
                cwd=str(ROOT_DIR),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(err_proc.returncode, 2)
            combined = err_proc.stdout + err_proc.stderr
            self.assertIn("OpenMaaS", combined)
            self.assertIn("scripts/eval_soc_agent.py", combined)


class TestModelCatalogShellHelpers(unittest.TestCase):
    """Validate scripts/lib/model_catalog.sh and scripts/vertex_model_register.sh."""

    def _run_catalog_cmd(self, bash_expr: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", "-c", f"source scripts/lib/model_catalog.sh && {bash_expr}"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            check=False,
        )

    def test_shell_catalog_helpers(self):
        checks = [
            (
                'catalog_get_maas_model_id "deepseek-v4.1-flash-1017-maas"',
                "deepseek-ai/deepseek-v4.1-flash-1017-maas",
            ),
            (
                'catalog_get_maas_model_id "deepseek-v4.1-flash-maas"',
                "deepseek-ai/deepseek-v4.1-flash-maas",
            ),
            ('catalog_get_maas_model_id "grok-4.6"', "xai/grok-4.6"),
            ('catalog_get_deployment_timeout "deepseek-v4.1-flash-1017"', "7200"),
            ('catalog_get_container_port "deepseek-v4.1-flash-1017"', "7080"),
            ('catalog_get_container_port "gemma-2-9b-it"', "8080"),
            ('catalog_get_predict_route "deepseek-v4.1-flash-1017"', "/generate"),
            ('catalog_get_health_route "deepseek-v4.1-flash-1017"', "/ping"),
            ('catalog_get_shared_memory_mb "deepseek-v4.1-flash-1017"', "40960"),
        ]
        for cmd, expected in checks:
            proc = self._run_catalog_cmd(cmd)
            self.assertEqual(proc.returncode, 0, msg=f"{cmd} failed: {proc.stderr}")
            self.assertEqual(proc.stdout.strip(), expected, msg=f"Mismatch for {cmd}")

        extra_proc = self._run_catalog_cmd('catalog_get_extra_args "deepseek-v4.1-flash-1017"')
        self.assertEqual(extra_proc.returncode, 0)
        self.assertEqual(extra_proc.stdout.strip().splitlines(), EXPECTED_EXTRA_ARGS)

    def test_vertex_model_register_rejects_maas_flavors(self):
        for maas_flavor in ("deepseek-v4.1-flash-1017-maas", "deepseek-v4.1-flash-maas"):
            proc = subprocess.run(
                ["bash", "scripts/vertex_model_register.sh", maas_flavor, "us-central1"],
                cwd=str(ROOT_DIR),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("OpenMaaS", proc.stderr)
            self.assertIn("scripts/eval_soc_agent.py", proc.stderr)

    def test_vertex_model_register_wires_port_routes_shm_and_timeout_with_stub_gcloud(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            log_file = tmp_path / "gcloud_calls.log"
            stub_gcloud = tmp_path / "gcloud"
            stub_gcloud.write_text(
                "#!/usr/bin/env bash\n"
                f'printf "%s\\n" "$*" >> "{log_file}"\n'
                'if [[ "$*" == *"models list"* ]]; then\n'
                '  if [[ -f "' + str(tmp_path / "uploaded") + '" ]]; then\n'
                '    echo "9988776655"\n'
                "  fi\n"
                'elif [[ "$*" == *"models upload"* ]]; then\n'
                '  touch "' + str(tmp_path / "uploaded") + '"\n'
                "fi\n",
                encoding="utf-8",
            )
            stub_gcloud.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{tmp_path}:{env.get('PATH', '')}"

            proc = subprocess.run(
                ["bash", "scripts/vertex_model_register.sh", "deepseek-v4.1-flash-1017", "us-central1"],
                cwd=str(ROOT_DIR),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertEqual(proc.stdout.strip(), "9988776655")

            logged = log_file.read_text(encoding="utf-8")
            self.assertIn("--container-ports=7080", logged)
            self.assertIn("--container-predict-route=/generate", logged)
            self.assertIn("--container-health-route=/ping", logged)
            self.assertIn("--container-shared-memory-size-mb=40960", logged)
            self.assertIn("--container-deployment-timeout-seconds=7200", logged)
            self.assertIn("MODEL_ID=deepseek-ai/DeepSeek-V4.1-Flash-1017", logged)
            self.assertIn("LOCAL_MODEL_DIR=/dev/shm/model_dir", logged)
            self.assertIn("--port=7080", logged)
            self.assertIn("--model=deepseek-ai/DeepSeek-V4.1-Flash-1017", logged)
            self.assertIn("--tensor-parallel-size=8", logged)
            self.assertIn("--max-model-len=1048576", logged)
            for flag in EXPECTED_EXTRA_ARGS:
                self.assertIn(flag, logged)


class TestOwnedFilesHygiene(unittest.TestCase):
    """Ensure owned files have zero em-dashes, emojis, or internal paths."""

    def test_owned_files_have_no_em_dashes_or_emojis(self):
        owned_paths = [
            ROOT_DIR / "configs" / "models.json",
            ROOT_DIR / "scripts" / "deploy_open_model.py",
            ROOT_DIR / "scripts" / "lib" / "model_catalog.sh",
            ROOT_DIR / "scripts" / "vertex_model_register.sh",
            ROOT_DIR / "tests" / "test_deepseek_v41_catalog.py",
        ]
        forbidden_tokens = [
            "\u2014",
            "corp.google" + ".com",
            "/usr/local/" + "google/home",
            "Argo" + "lis",
        ]
        for path in owned_paths:
            text = path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                self.assertNotIn(token, text, f"Forbidden token '{token}' found in {path.name}")
            for ch in text:
                code = ord(ch)
                is_emoji = (
                    (0x1F300 <= code <= 0x1FAFF)
                    or (0x2600 <= code <= 0x27BF)
                )
                self.assertFalse(is_emoji, f"Emoji character U+{code:04X} found in {path.name}")


if __name__ == "__main__":
    unittest.main()
