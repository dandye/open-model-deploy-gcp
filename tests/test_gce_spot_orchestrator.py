"""Unit tests for GCE Spot Sweep Orchestrator."""

import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock, patch
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.run_gce_spot_sweep import (
    ALL_GCE_SPOT_TARGETS,
    GCESpotOrchestrator,
    GCESpotTarget,
    build_gce_spot_create_command,
    main,
)


def test_gce_spot_target_initialization():
    """Verify GCESpotTarget fields and defaults."""
    target = GCESpotTarget(
        flavor="gemma-3-4b-it",
        hf_repo="google/gemma-3-4b-it",
        machine_type="g2-standard-8",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4",
        notes="Gemma 3 4B Multimodal",
    )
    assert target.flavor == "gemma-3-4b-it"
    assert target.hf_repo == "google/gemma-3-4b-it"
    assert target.machine_type == "g2-standard-8"
    assert target.accelerator_type == "nvidia-l4"
    assert target.accelerator_count == 1
    assert target.local_ssd_count == 1
    assert target.tensor_parallel_size == 1
    assert target.extra_vllm_flags == "--limit_mm_per_prompt=image=5 --max-num-seqs=4"
    assert target.notes == "Gemma 3 4B Multimodal"
    assert target.get_base_flavor() == "gemma-3-4b-it"


def test_gce_spot_target_base_flavor_resolution():
    """Verify base flavor stripping for optimization variants."""
    target_fp8 = GCESpotTarget(
        flavor="gemma-3-27b-it-fp8",
        hf_repo="google/gemma-3-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="nvidia-l4",
        accelerator_count=4,
        local_ssd_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8",
    )
    assert target_fp8.get_base_flavor() == "gemma-3-27b-it"

    target_spec = GCESpotTarget(
        flavor="gemma-4-31b-it-speculative",
        hf_repo="google/gemma-4-31B-it",
        machine_type="a2-highgpu-2g",
        accelerator_type="nvidia-tesla-a100",
        accelerator_count=2,
        local_ssd_count=2,
        tensor_parallel_size=2,
        extra_vllm_flags="--speculative-model=[ngram]",
    )
    assert target_spec.get_base_flavor() == "gemma-4-31b-it"

    target_caching = GCESpotTarget(
        flavor="gemma-3-27b-it-caching",
        hf_repo="google/gemma-3-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="nvidia-l4",
        accelerator_count=4,
        local_ssd_count=4,
        tensor_parallel_size=4,
    )
    assert target_caching.get_base_flavor() == "gemma-3-27b-it"


def test_gce_spot_command_builder_for_1x_l4():
    """Verify gcloud compute instances create command arguments for 1x L4."""
    target = GCESpotTarget(
        flavor="gemma-2-2b-it",
        hf_repo="google/gemma-2-2b-it",
        machine_type="g2-standard-4",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
        tensor_parallel_size=1,
    )
    cmd = build_gce_spot_create_command(
        target=target,
        project_id="test-project",
        zone="us-central1-a",
        output_gcs_uri="gs://test-bucket/results",
        instance_name="spot-test-instance",
    )
    assert cmd[0] == "gcloud"
    assert cmd[1] == "compute"
    assert cmd[2] == "instances"
    assert cmd[3] == "create"
    assert cmd[4] == "spot-test-instance"
    assert "--project=test-project" in cmd
    assert "--zone=us-central1-a" in cmd
    assert "--machine-type=g2-standard-4" in cmd
    assert "--provisioning-model=SPOT" in cmd
    assert "--instance-termination-action=DELETE" in cmd
    assert "--maintenance-policy=TERMINATE" in cmd
    assert "--accelerator=type=nvidia-l4,count=1" in cmd
    assert cmd.count("--local-ssd=interface=NVME") == 1
    assert "--scopes=cloud-platform" in cmd


def test_gce_spot_command_builder_for_4x_l4():
    """Verify gcloud compute instances create command arguments for 4x L4."""
    target = GCESpotTarget(
        flavor="gemma-3-27b-it",
        hf_repo="google/gemma-3-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="nvidia-l4",
        accelerator_count=4,
        local_ssd_count=4,
        tensor_parallel_size=4,
    )
    cmd = build_gce_spot_create_command(
        target=target,
        project_id="secops-demo-env",
        zone="europe-west4-a",
        output_gcs_uri="gs://bucket/out",
    )
    assert "--provisioning-model=SPOT" in cmd
    assert "--machine-type=g2-standard-48" in cmd
    assert "--accelerator=type=nvidia-l4,count=4" in cmd
    assert cmd.count("--local-ssd=interface=NVME") == 4
    assert "--project=secops-demo-env" in cmd
    assert "--zone=europe-west4-a" in cmd
    assert "--instance-termination-action=DELETE" in cmd
    assert "--maintenance-policy=TERMINATE" in cmd


def test_gce_spot_command_builder_for_2x_a100():
    """Verify gcloud compute instances create command arguments for 2x A100."""
    target = GCESpotTarget(
        flavor="gemma-4-31b-it",
        hf_repo="google/gemma-4-31B-it",
        machine_type="a2-highgpu-2g",
        accelerator_type="nvidia-tesla-a100",
        accelerator_count=2,
        local_ssd_count=2,
        tensor_parallel_size=2,
        extra_vllm_flags="--max-num-seqs=16",
    )
    cmd = build_gce_spot_create_command(
        target=target,
        project_id="test-project",
        zone="us-east1-c",
        output_gcs_uri="gs://test-bucket/results",
        hf_token="test_hf_token",
    )
    assert "--machine-type=a2-highgpu-2g" in cmd
    assert "--accelerator=type=nvidia-tesla-a100,count=2" in cmd
    assert cmd.count("--local-ssd=interface=NVME") == 2
    assert "--provisioning-model=SPOT" in cmd
    assert "--instance-termination-action=DELETE" in cmd
    assert "--maintenance-policy=TERMINATE" in cmd


def test_catalog_completeness():
    """Verify ALL_GCE_SPOT_TARGETS contains all required Gemma and partner model targets."""
    flavors = [t.flavor for t in ALL_GCE_SPOT_TARGETS]

    # Gemma 2 family
    assert "gemma-2-2b-it" in flavors
    assert "gemma-2-2b-it-speculative" in flavors
    assert "gemma-2-9b-it" in flavors
    assert "gemma-2-9b-it-fp8" in flavors
    assert "gemma-2-9b-it-speculative" in flavors
    assert "gemma-2-27b-it" in flavors
    assert "gemma-2-27b-it-fp8" in flavors
    assert "gemma-2-27b-it-speculative" in flavors

    # Gemma 3 family
    assert "gemma-3-1b-it" in flavors
    assert "gemma-3-1b-it-speculative" in flavors
    assert "gemma-3-4b-it" in flavors
    assert "gemma-3-4b-it-speculative" in flavors
    assert "gemma-3-12b-it" in flavors
    assert "gemma-3-12b-it-fp8" in flavors
    assert "gemma-3-12b-it-speculative" in flavors
    assert "gemma-3-27b-it" in flavors
    assert "gemma-3-27b-it-fp8" in flavors
    assert "gemma-3-27b-it-speculative" in flavors
    assert "gemma-3-27b-it-caching" in flavors

    # Gemma 4 family
    assert "gemma-4-e2b-it" in flavors
    assert "gemma-4-e2b-it-speculative" in flavors
    assert "gemma-4-e4b-it" in flavors
    assert "gemma-4-e4b-it-speculative" in flavors
    assert "gemma-4-31b-it" in flavors
    assert "gemma-4-31b-it-speculative" in flavors

    # Partner and Open models
    assert "inkling-small" in flavors
    assert "nemotron-3.5-lightning-bf16" in flavors
    assert "qwen2.5-coder-32b-instruct" in flavors
    assert "deepseek-r1-distill-qwen-32b" in flavors
    assert "ministral-3b-2410" in flavors
    assert "phi-4" in flavors
    assert "llama-3.2-3b-instruct" in flavors
    assert "llama-guard-3-8b" in flavors
    assert "llama-3.1-nemotron-70b-instruct" in flavors


def test_orchestrator_initialization():
    """Verify GCESpotOrchestrator initial state and parameter assignments."""
    orch = GCESpotOrchestrator(
        project_id="my-project",
        zone="europe-west4-b",
        output_gcs_bucket="gs://my-bucket/evals",
        dry_run=True,
        timeout_seconds=1800,
    )
    assert orch.project_id == "my-project"
    assert orch.zone == "europe-west4-b"
    assert orch.output_gcs_bucket == "gs://my-bucket/evals"
    assert orch.dry_run is True
    assert orch.timeout_seconds == 1800


def test_orchestrator_dry_run_launch():
    """Verify launch_instance in dry run mode."""
    orch = GCESpotOrchestrator(dry_run=True)
    target = ALL_GCE_SPOT_TARGETS[0]
    instance_name = orch.launch_instance(target)
    assert isinstance(instance_name, str)
    assert target.flavor in instance_name or "spot" in instance_name


def test_orchestrator_dry_run_monitor():
    """Verify monitor_instance_serial in dry run mode."""
    orch = GCESpotOrchestrator(dry_run=True)
    res = orch.monitor_instance_serial("spot-mock-instance", timeout_seconds=10)
    assert res is True


def test_orchestrator_dry_run_collect_results():
    """Verify collect_results in dry run mode."""
    orch = GCESpotOrchestrator(dry_run=True)
    target = ALL_GCE_SPOT_TARGETS[0]
    res = orch.collect_results(target)
    assert isinstance(res, dict)
    assert res.get("flavor") == target.flavor
    assert res["status"] == "SYNTHETIC"
    assert res["synthetic"] is True
    assert res["summary"] is None


def test_orchestrator_dry_run_sweep_execution():
    """Verify run_sweep in dry run mode with model filtering."""
    orch = GCESpotOrchestrator(dry_run=True)
    results = orch.run_sweep(models_filter=["gemma-2-2b-it", "gemma-3-1b-it"], wait=True)
    assert len(results) == 2
    flavors = [r["flavor"] for r in results]
    assert "gemma-2-2b-it" in flavors
    assert "gemma-3-1b-it" in flavors
    assert results[0]["status"] == "SYNTHETIC"


def test_orchestrator_live_launch_mocked():
    """Verify launch_instance executes gcloud compute instances create."""
    orch = GCESpotOrchestrator(project_id="test-proj", zone="us-central1-a", dry_run=False)
    target = GCESpotTarget(
        flavor="gemma-3-1b-it",
        hf_repo="google/gemma-3-1b-it",
        machine_type="g2-standard-4",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
    )

    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = "Created instance spot-gemma-3-1b-it.\n"
    mock_res.stderr = ""

    with patch("subprocess.run", return_value=mock_res) as mock_sub:
        name = orch.launch_instance(target, instance_name="custom-spot-1b")
        assert name == "custom-spot-1b"
        mock_sub.assert_called_once()
        args, kwargs = mock_sub.call_args
        cmd = args[0]
        assert "instances" in cmd
        assert "create" in cmd
        assert "custom-spot-1b" in cmd
        assert "--provisioning-model=SPOT" in cmd


def test_orchestrator_live_launch_failure_raises():
    """Verify launch_instance raises RuntimeError when gcloud returns non-zero."""
    orch = GCESpotOrchestrator(project_id="test-proj", zone="us-central1-a", dry_run=False)
    target = ALL_GCE_SPOT_TARGETS[0]

    mock_res = MagicMock()
    mock_res.returncode = 1
    mock_res.stdout = ""
    mock_res.stderr = "ERROR: (gcloud.compute.instances.create) Quota exceeded."

    with patch("subprocess.run", return_value=mock_res):
        with pytest.raises(RuntimeError, match="Quota exceeded"):
            orch.launch_instance(target)


def test_orchestrator_live_monitor_mocked():
    """Verify monitor_instance_serial checks instance status and returns True upon deletion."""
    orch = GCESpotOrchestrator(project_id="test-proj", zone="us-central1-a", dry_run=False)

    # First call: RUNNING, Second call: NOT_FOUND (instance deleted)
    mock_running = MagicMock(returncode=0, stdout="RUNNING\n")
    mock_deleted = MagicMock(returncode=1, stdout="", stderr="ERROR: The resource was not found")

    with patch("subprocess.run", side_effect=[mock_running, mock_deleted]), \
         patch("time.sleep", return_value=None):
        res = orch.monitor_instance_serial("test-inst", timeout_seconds=60)
        assert res is True


def test_orchestrator_live_monitor_does_not_treat_auth_error_as_deletion():
    """A describe permission/network error cannot verify instance deletion."""
    orch = GCESpotOrchestrator(project_id="test-proj", zone="us-central1-a", dry_run=False)
    error = MagicMock(returncode=1, stdout="", stderr="ERROR: permission denied")
    with patch("subprocess.run", return_value=error):
        res = orch.monitor_instance_serial("test-inst", timeout_seconds=60)
    assert res is False
    assert orch.last_monitor_outcome == "STATE_CHECK_FAILED"


def test_orchestrator_live_collect_results_mocked(tmp_path: Path):
    """Verify collect_results downloads and parses json report."""
    orch = GCESpotOrchestrator(
        project_id="test-proj",
        zone="us-central1-a",
        output_gcs_bucket="gs://test-bucket/evals",
        dry_run=False,
    )
    target = GCESpotTarget(
        flavor="gemma-2-2b-it",
        hf_repo="google/gemma-2-2b-it",
        machine_type="g2-standard-4",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
    )

    mock_report = {
        "flavor": "gemma-2-2b-it",
        "summary": {
            "total_cases": 5,
            "passed_cases": 5,
            "pass_rate": 100.0,
            "avg_rubric_score": 92.0,
        },
        "case_results": [],
    }

    def fake_subprocess_run(cmd, **kwargs):
        # Simulate gcloud storage cp creating the json file in tmpdir
        dest = cmd[-1]
        dest_path = Path(dest)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(mock_report, f)
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        res = orch.collect_results(target, output_dir=tmp_path)
        assert res["flavor"] == "gemma-2-2b-it"
        assert res["summary"]["pass_rate"] == 100.0


def test_collect_results_preserves_failed_artifact_status(tmp_path: Path):
    """A failed startup artifact must not be reclassified as completed."""
    orch = GCESpotOrchestrator(
        project_id="test-proj",
        zone="us-central1-a",
        output_gcs_bucket="gs://test-bucket/evals",
        dry_run=False,
    )
    target = ALL_GCE_SPOT_TARGETS[0]
    failed_report = {
        "flavor": target.flavor,
        "status": "FAILED",
        "evaluation": {"evaluator_exit_status": 127},
        "summary": None,
    }

    def fake_subprocess_run(cmd, **kwargs):
        Path(cmd[-1]).write_text(json.dumps(failed_report), encoding="utf-8")
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        result = orch.collect_results(target, output_dir=tmp_path)
    assert result["status"] == "FAILED"
    assert result["evaluation"]["evaluator_exit_status"] == 127


def test_collect_results_marks_missing_status_unverified(tmp_path: Path):
    """Legacy artifacts without lifecycle status cannot claim completion."""
    orch = GCESpotOrchestrator(output_gcs_bucket="gs://test-bucket/evals", dry_run=False)
    target = ALL_GCE_SPOT_TARGETS[0]

    def fake_subprocess_run(cmd, **kwargs):
        Path(cmd[-1]).write_text(json.dumps({"flavor": target.flavor}), encoding="utf-8")
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        result = orch.collect_results(target, output_dir=tmp_path)
    assert result["status"] == "UNVERIFIED"


def test_run_sweep_preserves_evaluation_failure_when_monitoring_times_out():
    """Monitoring timeout is recorded alongside, rather than over, evaluator failure."""
    orch = GCESpotOrchestrator(dry_run=False, timeout_seconds=12)
    target = ALL_GCE_SPOT_TARGETS[0]
    with patch.object(orch, "launch_instance", return_value="spot-test"), \
         patch.object(orch, "monitor_instance_serial", return_value=False) as monitor, \
         patch.object(orch, "collect_results", return_value={"flavor": target.flavor, "status": "FAILED", "error": "evaluator exit 23"}):
        orch.last_monitor_outcome = "TIMED_OUT"
        result = orch.run_sweep(models_filter=[target.flavor])
    monitor.assert_called_once()
    assert result[0]["status"] == "FAILED"
    assert result[0]["monitoring"]["status"] == "TIMED_OUT"


def test_run_sweep_marks_terminal_instance_without_absence_verification():
    """A stopped VM is terminal, but its deletion still needs verification."""
    orch = GCESpotOrchestrator(dry_run=False, timeout_seconds=12)
    target = ALL_GCE_SPOT_TARGETS[0]
    with patch.object(orch, "launch_instance", return_value="spot-test"), \
         patch.object(orch, "monitor_instance_serial", return_value=True), \
         patch.object(orch, "collect_results", return_value={"flavor": target.flavor, "status": "COMPLETED"}):
        orch.last_monitor_outcome = "STOPPED_NOT_DELETED"
        result = orch.run_sweep(models_filter=[target.flavor])
    assert result[0]["status"] == "CLEANUP_UNVERIFIED"
    assert result[0]["evaluation_status"] == "COMPLETED"


def test_cli_main_dry_run():
    """Verify main() CLI execution with --dry-run flag."""
    test_args = [
        "run_gce_spot_sweep.py",
        "--models", "gemma-2-2b-it",
        "--dry-run",
        "--project-id", "test-proj",
        "--zone", "us-central1-a",
    ]
    with patch.object(sys, "argv", test_args):
        # Should execute successfully without throwing exception
        main()


def test_no_emojis_in_gce_spot_orchestrator_files():
    """Verify zero emojis in orchestrator script and test file."""
    for filename in ["scripts/run_gce_spot_sweep.py", "tests/test_gce_spot_orchestrator.py"]:
        path = ROOT_DIR / filename
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        for char in content:
            code_point = ord(char)
            is_emoji = (
                (0x1F600 <= code_point <= 0x1F64F)
                or (0x1F300 <= code_point <= 0x1F5FF)
                or (0x1F680 <= code_point <= 0x1F6FF)
                or (0x2600 <= code_point <= 0x26FF)
                or (0x2700 <= code_point <= 0x27BF)
                or (0x1F900 <= code_point <= 0x1F9FF)
                or (0x1FA70 <= code_point <= 0x1FAFF)
            )
            assert not is_emoji, f"Found emoji '{char}' (code {code_point:#x}) in {filename}"
