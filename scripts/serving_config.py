"""Validation and identity helpers for pinned model serving configuration."""

import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Dict, Optional


_TOP_KEYS = {"schema_version", "target_flavor", "model_repository", "model_revision",
             "serving_image", "evaluator_image", "boot_image", "parameters"}
_REVISION = re.compile(r"[0-9a-f]{40}\Z")
_HF_REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
_IMAGE = re.compile(r"[A-Za-z0-9.-]+(?::[0-9]+)?(?:/[A-Za-z0-9._-]+)+@sha256:[0-9a-f]{64}\Z")
_BOOT = re.compile(r"projects/[a-z][a-z0-9-]*/global/images/[a-z][a-z0-9-]*\Z")
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")


def validate_serving_config(config: Dict[str, Any], target: Optional[Any] = None) -> None:
    if not isinstance(config, dict) or set(config) != _TOP_KEYS:
        raise ValueError("serving configuration has unexpected or missing fields")
    if type(config["schema_version"]) is not int or config["schema_version"] != 1:
        raise ValueError("unsupported serving configuration schema")
    flavor = config["target_flavor"]
    if not isinstance(flavor, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", flavor):
        raise ValueError("invalid target_flavor")
    if not isinstance(config["model_repository"], str) or not _HF_REPO.fullmatch(config["model_repository"]):
        raise ValueError("invalid model_repository")
    if not isinstance(config["model_revision"], str) or not _REVISION.fullmatch(config["model_revision"]):
        raise ValueError("model_revision must be lowercase full commit SHA")
    for field in ("serving_image", "evaluator_image"):
        value = config[field]
        if not isinstance(value, str) or any(c.isspace() for c in value) or "|~|" in value or not _IMAGE.fullmatch(value):
            raise ValueError(f"invalid {field}")
    if not isinstance(config["boot_image"], str) or not _BOOT.fullmatch(config["boot_image"]):
        raise ValueError("invalid boot_image")
    params = config["parameters"]
    if not isinstance(params, dict) or set(params) != {"tensor_parallel_size", "max_model_len", "gpu_memory_utilization"}:
        raise ValueError("parameters must contain exactly the pinned serving parameters")
    for field in ("tensor_parallel_size", "max_model_len"):
        value = params[field]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or (field == "tensor_parallel_size" and value > 64):
            raise ValueError(f"invalid {field}")
    gpu = params["gpu_memory_utilization"]
    if isinstance(gpu, bool) or not isinstance(gpu, (int, float)) or not math.isfinite(gpu) or not 0 < gpu < 1:
        raise ValueError("invalid gpu_memory_utilization")
    if target is not None:
        values = target if isinstance(target, dict) else vars(target)
        if values.get("flavor") != flavor or values.get("hf_repo") != config["model_repository"] or values.get("tensor_parallel_size") != params["tensor_parallel_size"]:
            raise ValueError("serving configuration does not match target")
        if values.get("extra_vllm_flags"):
            raise ValueError("target extra_vllm_flags cannot override pinned serving configuration")


def serving_config_hash(config: Dict[str, Any]) -> str:
    validate_serving_config(config)
    payload = json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(payload).hexdigest()


def load_serving_config(path: Path) -> Dict[str, Any]:
    try:
        config = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(f"invalid serving configuration file: {path}") from exc
    validate_serving_config(config)
    return config


def serving_evidence_matches(observed: Dict[str, Any], expected: Dict[str, Any]) -> bool:
    try:
        validate_serving_config(expected)
        if not isinstance(observed, dict) or observed.get("status") != "PINNED_IMAGES_VERIFIED":
            return False
        if observed.get("scope") != "container_image_ids_and_requested_model_revision":
            return False
        if observed.get("configuration") != expected or observed.get("configuration_hash") != serving_config_hash(expected):
            return False
        return (_HASH.fullmatch(observed.get("serving_image_id", "")) is not None
                and _HASH.fullmatch(observed.get("evaluator_image_id", "")) is not None)
    except (ValueError, TypeError, KeyError):
        return False
