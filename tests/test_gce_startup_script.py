"""Unit tests for GCE Spot self-terminating startup script and template."""

import os
from pathlib import Path
import stat
import subprocess
import tempfile
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
STARTUP_SCRIPT_PATH = ROOT_DIR / "scripts" / "gce_startup_script.sh"
STARTUP_TEMPLATE_PATH = ROOT_DIR / "scripts" / "templates" / "gce_startup_template.sh"


def test_startup_script_exists_and_executable():
    """Verify scripts/gce_startup_script.sh exists and is executable."""
    assert STARTUP_SCRIPT_PATH.exists(), f"Missing {STARTUP_SCRIPT_PATH}"
    file_stat = STARTUP_SCRIPT_PATH.stat()
    assert bool(file_stat.st_mode & stat.S_IXUSR), "Script is not user-executable"


def test_startup_script_syntax_validity():
    """Verify scripts/gce_startup_script.sh passes bash syntax check."""
    assert STARTUP_SCRIPT_PATH.exists(), f"Missing {STARTUP_SCRIPT_PATH}"
    res = subprocess.run(
        ["bash", "-n", str(STARTUP_SCRIPT_PATH)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"Bash syntax check failed: {res.stderr}"


def test_startup_script_no_emojis_or_non_ascii():
    """Verify scripts do not contain emojis or non-ascii characters."""
    for path in [STARTUP_SCRIPT_PATH, STARTUP_TEMPLATE_PATH]:
        if path.exists():
            content = path.read_text(encoding="utf-8")
            non_ascii = [char for char in content if ord(char) > 127]
            assert len(non_ascii) == 0, f"Found non-ASCII characters in {path}: {set(non_ascii)}"


def test_startup_script_strict_mode():
    """Verify script uses strict bash error handling."""
    assert STARTUP_SCRIPT_PATH.exists()
    content = STARTUP_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "set -euo pipefail" in content


def test_startup_script_metadata_queries():
    """Verify script queries GCE metadata server endpoints."""
    assert STARTUP_SCRIPT_PATH.exists()
    content = STARTUP_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "http://metadata.google.internal/computeMetadata/v1/" in content
    assert "Metadata-Flavor: Google" in content
    assert "instance/name" in content
    assert "instance/zone" in content
    assert "instance/attributes/model_flavor" in content
    assert "instance/attributes/hf_repo" in content
    assert "instance/attributes/tp_size" in content
    assert "instance/attributes/output_bucket" in content


def test_startup_script_nvme_scratch_mount():
    """Verify script mounts local NVMe SSD scratch disk."""
    assert STARTUP_SCRIPT_PATH.exists()
    content = STARTUP_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "google-local-nvme-ssd" in content or "nvme" in content
    assert "/mnt/disks/nvme" in content
    assert "mkfs.ext4" in content
    assert "HF_HOME" in content


def test_startup_script_docker_vllm_execution():
    """Verify script launches vLLM container with GPU flags."""
    assert STARTUP_SCRIPT_PATH.exists()
    content = STARTUP_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "docker run" in content
    assert "--gpus all" in content
    assert "--ipc=host" in content
    assert "vllm/vllm-openai:latest" in content or "vllm" in content
    assert "8080" in content


def test_startup_script_health_poll():
    """Verify script polls local vLLM health endpoint before running tests."""
    assert STARTUP_SCRIPT_PATH.exists()
    content = STARTUP_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "8080/health" in content or "8080/v1/models" in content


def test_startup_script_evaluation_invocation():
    """Verify script invokes SOC evaluation runner, benchmark, and fallback JSON generation."""
    assert STARTUP_SCRIPT_PATH.exists()
    content = STARTUP_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "eval_soc_agent.py" in content
    assert "--cloudrun-url" in content or "http://127.0.0.1:8080" in content
    assert "JSON_PATH" in content


def test_startup_script_gcs_upload():
    """Verify script uploads reports to Google Cloud Storage with fallback."""
    assert STARTUP_SCRIPT_PATH.exists()
    content = STARTUP_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "OUTPUT_BUCKET" in content
    assert "gcloud storage cp" in content or "gsutil" in content


def test_startup_script_self_deletion():
    """Verify script executes instance self-deletion and re-entrancy prevention."""
    assert STARTUP_SCRIPT_PATH.exists()
    content = STARTUP_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "gcloud compute instances delete" in content
    assert "--zone" in content
    assert "--quiet" in content
    assert "trap cleanup_and_self_delete" in content
    assert "trap - EXIT ERR INT TERM" in content


def test_startup_template_exists_and_has_placeholders():
    """Verify template exists with required placeholder tokens."""
    assert STARTUP_TEMPLATE_PATH.exists(), f"Missing {STARTUP_TEMPLATE_PATH}"
    content = STARTUP_TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "{{MODEL_FLAVOR}}" in content
    assert "{{HF_REPO}}" in content
    assert "{{TP_SIZE}}" in content
    assert "{{OUTPUT_BUCKET}}" in content
    assert "{{EXTRA_FLAGS}}" in content


def test_startup_template_substitution_logic():
    """Verify template substitution produces valid script."""
    assert STARTUP_TEMPLATE_PATH.exists()
    template_content = STARTUP_TEMPLATE_PATH.read_text(encoding="utf-8")
    rendered = template_content.replace("{{MODEL_FLAVOR}}", "gemma-3-27b-it")
    rendered = rendered.replace("{{HF_REPO}}", "google/gemma-3-27b-it")
    rendered = rendered.replace("{{TP_SIZE}}", "4")
    rendered = rendered.replace("{{OUTPUT_BUCKET}}", "gs://test-bucket/out")
    rendered = rendered.replace("{{EXTRA_FLAGS}}", "--enable-prefix-caching")
    rendered = rendered.replace("{{HF_TOKEN}}", "")
    rendered = rendered.replace("{{GCS_MODEL_PATH}}", "")

    assert "gemma-3-27b-it" in rendered
    assert "google/gemma-3-27b-it" in rendered
    assert "tp_size=4" in rendered or "TP_SIZE=4" in rendered or "4" in rendered
    assert "{{" not in rendered


def test_startup_template_rendered_syntax_validity():
    """Verify rendered template passes bash syntax check."""
    assert STARTUP_TEMPLATE_PATH.exists()
    template_content = STARTUP_TEMPLATE_PATH.read_text(encoding="utf-8")
    rendered = template_content.replace("{{MODEL_FLAVOR}}", "gemma-4-31b-it")
    rendered = rendered.replace("{{HF_REPO}}", "google/gemma-4-31b-it")
    rendered = rendered.replace("{{TP_SIZE}}", "2")
    rendered = rendered.replace("{{OUTPUT_BUCKET}}", "gs://my-bucket/results")
    rendered = rendered.replace("{{EXTRA_FLAGS}}", "--max-model-len 8192")
    rendered = rendered.replace("{{HF_TOKEN}}", "dummy_token")
    rendered = rendered.replace("{{GCS_MODEL_PATH}}", "gs://models/gemma-4-31b-it")

    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
        f.write(rendered)
        temp_path = f.name

    try:
        res = subprocess.run(
            ["bash", "-n", temp_path],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, f"Rendered template bash syntax check failed: {res.stderr}"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
