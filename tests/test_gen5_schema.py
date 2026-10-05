"""Gen 5 schema, pool, and template validity tests."""

import ipaddress
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from gen5_fixtures import GEN5_ROOT, minimal_family

SCHEMA_DIR = GEN5_ROOT / "schema"
POOLS_PATH = GEN5_ROOT / "pools" / "pools-v1.json"

REQUIRED_POOL_KEYS = [
    "pool_version", "description", "sites", "host_roles", "external_ip_cidr", "doc_ip_cidrs",
    "first_names", "last_names", "departments", "pii_departments", "domain_words", "tlds",
    "domain_styles", "infostealer_families", "ransomware_families", "encrypted_extensions",
    "ransom_notes", "payload_filenames", "scanner_products", "saas_vendors", "software_vendors",
    "vendor_tool_filenames", "registrars", "lateral_tools", "miner_process_names",
    "phishing_subjects", "network_test_tools", "sensitive_data_labels", "cloud_projects", "travel_cities",
]


def load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def strip_patterns(node):
    if isinstance(node, dict):
        return {k: strip_patterns(v) for k, v in node.items() if k != "pattern"}
    if isinstance(node, list):
        return [strip_patterns(v) for v in node]
    return node


def validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(load_schema(name))


@pytest.mark.parametrize("name", ["case", "family", "manifest"])
def test_schemas_are_valid_draft_2020_12(name):
    Draft202012Validator.check_schema(load_schema(name))


def test_family_defs_are_case_defs_without_patterns():
    case_defs = load_schema("case")["$defs"]
    family_defs = dict(load_schema("family")["$defs"])
    slot_def = family_defs.pop("slot")
    assert family_defs == strip_patterns(case_defs)
    assert set(slot_def["properties"]["type"]["enum"]) == {
        "hostname", "internal_ip", "external_ip", "doc_ip", "domain", "sha256", "username",
        "case_id", "ticket_id", "key_id", "timestamp", "integer", "choice",
    }


def test_pools_v1_shape():
    pools = json.loads(POOLS_PATH.read_text(encoding="utf-8"))
    assert list(pools)[: len(REQUIRED_POOL_KEYS)] == REQUIRED_POOL_KEYS
    assert pools["pool_version"] == "pools-v1"
    for key in REQUIRED_POOL_KEYS[6:]:
        values = pools[key]
        if isinstance(values, list):
            assert values, key
            assert len(values) == len(set(values)), f"duplicate entry in {key}"
            assert all(v.isascii() for v in values), key
    assert len(pools["first_names"]) >= 30 and len(pools["last_names"]) >= 30
    assert len(pools["domain_words"]) >= 30
    for style, template in pools["domain_styles"].items():
        assert "{tld}" in template and "{word}" in template, style
    for role, prefixes in pools["host_roles"].items():
        assert prefixes, role
        assert all(p.isupper() and 2 <= len(p) <= 4 for p in prefixes), role


def test_pools_v1_address_plan():
    pools = json.loads(POOLS_PATH.read_text(encoding="utf-8"))
    gen3_space = ipaddress.ip_network("10.0.0.0/16")
    private = ipaddress.ip_network("10.0.0.0/8")
    seen = []
    for code, site in pools["sites"].items():
        assert len(code) == 3 and code.isupper()
        net = ipaddress.ip_network(site["subnet"])
        assert net.prefixlen == 24
        assert net.subnet_of(private)
        assert not net.overlaps(gen3_space), f"{code} overlaps the Gen 3 range"
        assert all(not net.overlaps(other) for other in seen), f"{code} overlaps another site"
        seen.append(net)
    assert pools["external_ip_cidr"] == "198.18.0.0/15"
    assert pools["doc_ip_cidrs"] == ["192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24"]


def test_minimal_family_validates_against_family_schema():
    validator("family").validate(minimal_family())


def test_family_schema_rejects_unknown_top_level_field():
    family = minimal_family()
    family["split"] = "train"
    with pytest.raises(ValidationError):
        validator("family").validate(family)


def test_family_schema_rejects_unknown_slot_type():
    family = minimal_family()
    family["slots"]["host"]["type"] = "mac_address"
    with pytest.raises(ValidationError):
        validator("family").validate(family)


def test_case_schema_rejects_overlay_mode():
    case_schema = load_schema("case")
    env_validator = Draft202012Validator({"$ref": "#/$defs/environment_state", "$defs": case_schema["$defs"]})
    state = {"mode": "overlay", "hosts": {}, "ips": {}, "domains": {}, "hashes": {}, "cases": {}, "events": []}
    errors = list(env_validator.iter_errors(state))
    assert any(e.validator == "const" and list(e.path) == ["mode"] for e in errors)
    state["mode"] = "replace"
    assert not any(list(e.path) == ["mode"] for e in env_validator.iter_errors(state))


@pytest.mark.parametrize("path", sorted((GEN5_ROOT / "families").glob("FAM-*.json")) or [None])
def test_committed_families_validate(path):
    if path is None:
        pytest.skip("no family templates committed yet")
    family = json.loads(Path(path).read_text(encoding="utf-8"))
    validator("family").validate(family)
    assert family["family_id"] == Path(path).stem
