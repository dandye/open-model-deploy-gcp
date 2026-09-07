import copy
import json
from pathlib import Path

import pytest

from scripts.serving_config import load_serving_config, serving_config_hash, serving_evidence_matches, validate_serving_config


@pytest.fixture
def config():
    return {
        "schema_version": 1, "target_flavor": "gemma-2-2b-it", "model_repository": "google/gemma-2-2b-it",
        "model_revision": "a" * 40, "serving_image": "us-central1-docker.pkg.dev/proj/serving@sha256:" + "b" * 64,
        "evaluator_image": "registry.example:5000/team/eval@sha256:" + "c" * 64,
        "boot_image": "projects/proj-1/global/images/ubuntu-2404-v1",
        "parameters": {"tensor_parallel_size": 1, "max_model_len": 4096, "gpu_memory_utilization": 0.9},
    }


def test_valid_config_hash_and_load(tmp_path: Path, config):
    validate_serving_config(config)
    assert len(serving_config_hash(config)) == 64
    path = tmp_path / "serving.json"
    path.write_text(json.dumps(config))
    assert load_serving_config(path) == config


@pytest.mark.parametrize("field,value", [
    ("model_revision", "A" * 40), ("serving_image", "repo:latest"),
    ("boot_image", "projects/p/global/images/family/name"),
    ("parameters", {"tensor_parallel_size": True, "max_model_len": 1, "gpu_memory_utilization": 0.5}),
])
def test_invalid_pins_rejected(config, field, value):
    bad = copy.deepcopy(config); bad[field] = value
    with pytest.raises(ValueError):
        validate_serving_config(bad)


def test_unknown_fields_and_target_overrides_rejected(config):
    bad = copy.deepcopy(config); bad["extra"] = 1
    with pytest.raises(ValueError): validate_serving_config(bad)
    target = {"flavor": config["target_flavor"], "hf_repo": config["model_repository"], "tensor_parallel_size": 1, "extra_vllm_flags": "--served-model-name other"}
    with pytest.raises(ValueError): validate_serving_config(config, target)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 0, -1, "", True])
def test_malformed_numeric_parameters_rejected(config, value):
    bad = copy.deepcopy(config)
    bad["parameters"]["gpu_memory_utilization"] = value
    with pytest.raises(ValueError):
        validate_serving_config(bad)


def test_target_mismatch_rejected(config):
    for field, value in (("flavor", "other-model"), ("hf_repo", "other/model"), ("tensor_parallel_size", 2)):
        target = {"flavor": config["target_flavor"], "hf_repo": config["model_repository"],
                  "tensor_parallel_size": 1, "extra_vllm_flags": ""}
        target[field] = value
        with pytest.raises(ValueError):
            validate_serving_config(config, target)


def test_evidence_matching_is_strict_and_malformed_is_false(config):
    evidence = {"status": "PINNED_IMAGES_VERIFIED", "scope": "container_image_ids_and_requested_model_revision",
                "configuration": config, "configuration_hash": serving_config_hash(config),
                "serving_image_id": "sha256:" + "d" * 64, "evaluator_image_id": "sha256:" + "e" * 64}
    assert serving_evidence_matches(evidence, config)
    for key, value in (("status", "COMPLETED"), ("scope", "wrong"), ("serving_image_id", "bad"), ("configuration_hash", "0" * 64), ("evaluator_image_id", None)):
        bad = dict(evidence); bad[key] = value
        assert not serving_evidence_matches(bad, config)
    assert not serving_evidence_matches(None, config)
