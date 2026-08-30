import os
import re
import stat
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_dockerfile_custom_job_exists_and_valid():
    """Verifies that docker/Dockerfile.custom_job exists and meets requirements."""
    dockerfile_path = ROOT_DIR / "docker" / "Dockerfile.custom_job"
    assert dockerfile_path.exists(), f"Missing {dockerfile_path}"
    content = dockerfile_path.read_text(encoding="utf-8")

    # Base image verification
    assert "FROM vllm/vllm-openai" in content or "FROM python:" in content

    # Dependency installation verification
    assert "google-cloud-storage" in content
    assert "google-cloud-aiplatform" in content
    assert "pydantic" in content

    # Workdir and file copy verification
    assert "WORKDIR /workspace" in content
    assert "COPY agent/" in content or "COPY agent" in content
    assert "scripts/eval_soc_agent.py" in content
    assert "scripts/benchmark.py" in content
    assert "scripts/custom_job_entrypoint.sh" in content
    assert "configs/evals/soc_tier1_evalset.json" in content

    # Entrypoint configuration
    assert "ENTRYPOINT" in content
    assert "/workspace/scripts/custom_job_entrypoint.sh" in content


def test_entrypoint_script_syntax_and_permissions():
    """Verifies custom_job_entrypoint.sh existence, executable permissions, and bash syntax."""
    script_path = ROOT_DIR / "scripts" / "custom_job_entrypoint.sh"
    assert script_path.exists(), f"Missing {script_path}"

    # Verify executable bit
    mode = os.stat(script_path).st_mode
    is_executable = bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
    assert is_executable, f"{script_path} is not executable"

    content = script_path.read_text(encoding="utf-8")

    # Shebang and safety flags
    assert content.startswith("#!/usr/bin/env bash") or content.startswith("#!/bin/bash")
    assert "set -euo pipefail" in content

    # Validate bash syntax using bash -n
    proc = subprocess.run(["bash", "-n", str(script_path)], capture_output=True, text=True)
    assert proc.returncode == 0, f"Bash syntax check failed: {proc.stderr}"


def test_entrypoint_script_arguments_and_flow():
    """Verifies argument parsing, vllm invocation, health polling, evals, and gcs upload."""
    script_path = ROOT_DIR / "scripts" / "custom_job_entrypoint.sh"
    content = script_path.read_text(encoding="utf-8")

    # Argument parsing
    assert "MODEL_FLAVOR=" in content
    assert "HF_REPO=" in content
    assert "TENSOR_PARALLEL_SIZE=" in content
    assert "EXTRA_FLAGS=" in content
    assert "OUTPUT_GCS_PATH=" in content

    # vLLM launch & health check
    assert "vllm" in content
    assert "8080" in content
    assert "/health" in content or "/v1/models" in content

    # Evaluation runner invocation
    assert "eval_soc_agent.py" in content
    assert "soc_tier1_evalset.json" in content

    # GCS upload mechanism
    assert "gsutil" in content or "gcloud storage" in content or "google.cloud.storage" in content

    # Clean process termination / trap
    assert "trap" in content
    assert "kill" in content


def test_no_emojis_in_custom_job_files():
    """Verifies that no emojis exist in Dockerfile, entrypoint script, or tests."""
    files_to_check = [
        ROOT_DIR / "docker" / "Dockerfile.custom_job",
        ROOT_DIR / "scripts" / "custom_job_entrypoint.sh",
        Path(__file__),
    ]

    for file_path in files_to_check:
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            for line_idx, line in enumerate(content.splitlines(), start=1):
                for char in line:
                    assert ord(char) <= 127, (
                        f"Non-ASCII / emoji character '{char}' (ord {ord(char)}) "
                        f"found at {file_path}:{line_idx}"
                    )
