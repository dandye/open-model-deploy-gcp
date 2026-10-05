"""Contract tests over the committed Gen 5 suite in configs/evals/gen5.

Unlike tests/test_gen5_instancer.py, which builds a minimal family in a
temporary root, these tests read the checked-in bundles and manifest and
fail when they drift from a fresh build or break a suite-level rule.
"""
from __future__ import annotations

import ipaddress
import json
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List

import pytest

from agent.soc_environment import SocEnvironment
from scripts import gen5_instancer as inst

ROOT = inst.GEN5_ROOT
EXPECTED_SPLIT_SIZES = {"train": 40, "validation": 20, "final_test": 30}
EXPECTED_FAMILY_COUNT = 16
HOST_RE = re.compile(r"^[A-Z]{2,4}-[A-Z]{3}-[0-9]{2}$")
DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$")
SEEN_SPLIT_BY_INDEX = {0: "train", 1: "train", 2: "train", 3: "train", 4: "validation", 5: "final_test"}


def _load(name: str) -> Dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


@pytest.fixture(scope="module")
def manifest() -> Dict[str, Any]:
    return _load(inst.MANIFEST_FILE)


@pytest.fixture(scope="module")
def bundles() -> Dict[str, Dict[str, Any]]:
    return {split: _load(inst.BUNDLE_FILES[split]) for split in inst.SPLITS}


@pytest.fixture(scope="module")
def all_cases(bundles: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [case for split in inst.SPLITS for case in bundles[split]["eval_cases"]]


@pytest.fixture(scope="module")
def reserved() -> List[str]:
    return [str(value) for value in _load("pools/reserved_literals.json")["literals"]]


def test_check_is_clean(capsys: pytest.CaptureFixture[str]) -> None:
    assert inst.main(["check"]) == 0
    assert "check: clean" in capsys.readouterr().out


def test_split_sizes_and_manifest_agree(bundles: Dict[str, Dict[str, Any]], manifest: Dict[str, Any]) -> None:
    for split in inst.SPLITS:
        bundle = bundles[split]
        assert bundle["evalset_id"] == inst.EVALSET_ID
        assert bundle["generation"] == 5
        assert bundle["split"] == split
        assert len(bundle["eval_cases"]) == EXPECTED_SPLIT_SIZES[split]
        assert [case["eval_id"] for case in bundle["eval_cases"]] == manifest["splits"][split]
    assert len(manifest["families"]) == EXPECTED_FAMILY_COUNT
    assert len(manifest["cases"]) == sum(EXPECTED_SPLIT_SIZES.values())


def test_manifest_hashes_match_bundle_bytes(all_cases: List[Dict[str, Any]], manifest: Dict[str, Any]) -> None:
    expected = {entry["eval_id"]: entry["case_sha256"] for entry in manifest["cases"]}
    for case in all_cases:
        assert inst.sha256_text(inst.canonical_json(case)) == expected[case["eval_id"]], case["eval_id"]
    assert manifest["forbidden_literals_sha256"] == inst.sha256_text(inst.canonical_json(manifest["forbidden_literals"]))


def test_every_case_validates_against_the_schema(all_cases: List[Dict[str, Any]]) -> None:
    for case in all_cases:
        inst.validate_with_schema(ROOT, "case", case, case["eval_id"])
        assert case["generation"] == 5
        assert case["eval_id"] == f"CASE-GEN5-{inst.family_short_id(case['family_id'])}-{case['instance_index'] + 1:02d}"


def test_identifying_literals_are_unique_and_outside_gen3(manifest: Dict[str, Any], reserved: List[str]) -> None:
    counts: Counter[str] = Counter()
    for entry in manifest["cases"]:
        counts.update(literal.lower() for literal in entry["literals"])
    repeated = sorted(literal for literal, count in counts.items() if count > 1)
    assert repeated == [], f"identifying literals shared by two cases: {repeated}"
    reserved_lower = {literal.lower() for literal in reserved}
    leaked = sorted(set(counts) & reserved_lower)
    assert leaked == [], f"Gen 3 literals reused: {leaked}"
    forbidden = set(manifest["forbidden_literals"])
    assert reserved_lower <= {literal.lower() for literal in forbidden}
    assert all(literal in forbidden for entry in manifest["cases"] for literal in entry["literals"])


def test_split_roles_follow_the_plan(manifest: Dict[str, Any]) -> None:
    role_by_family = {entry["family_id"]: entry["split_role"] for entry in manifest["families"]}
    for entry in manifest["cases"]:
        role = role_by_family[entry["family_id"]]
        if role == "seen":
            assert entry["split"] == SEEN_SPLIT_BY_INDEX[entry["instance_index"]], entry["eval_id"]
        elif role == "validation_ood":
            assert entry["split"] == "validation", entry["eval_id"]
        else:
            assert role == "final_test_ood"
            assert entry["split"] == "final_test", entry["eval_id"]


def test_family_shape_is_fixed_per_family(all_cases: List[Dict[str, Any]]) -> None:
    shapes: Dict[str, set] = defaultdict(set)
    for case in all_cases:
        shapes[case["family_id"]].add(json.dumps({
            "label": case["ground_truth_label"],
            "criticality": case["asset_criticality"],
            "difficulty": case["difficulty"],
            "expected": sorted(case["expected_actions"]),
            "prohibited": sorted(case["prohibited_actions"]),
            "pair": case["counterfactual_pair_id"],
            "fault": case["fault_injection"],
            "liveness": case["liveness"],
        }, sort_keys=True))
    for family_id, variants in shapes.items():
        assert len(variants) == 1, f"{family_id} instances differ in a fixed field"


def test_counterfactual_pairs_do_not_straddle_split_roles(manifest: Dict[str, Any], all_cases: List[Dict[str, Any]]) -> None:
    role_by_family = {entry["family_id"]: entry["split_role"] for entry in manifest["families"]}
    roles_by_pair: Dict[str, set] = defaultdict(set)
    for case in all_cases:
        if case["counterfactual_pair_id"]:
            roles_by_pair[case["counterfactual_pair_id"]].add(role_by_family[case["family_id"]])
    for pair_id, roles in roles_by_pair.items():
        assert len(roles) == 1, f"{pair_id} spans split roles {sorted(roles)}"


def test_prohibited_entities_are_named_and_discoverable(all_cases: List[Dict[str, Any]]) -> None:
    for case in all_cases:
        prompt = case["prompt"].lower()
        assert case["prohibited_entities"], case["eval_id"]
        for entity in case["prohibited_entities"]:
            assert entity.lower() in prompt, f"{case['eval_id']}: {entity} not in prompt"
        discoverable = [e for e in case["prohibited_entities"] if HOST_RE.match(e) or _is_ip(e) or DOMAIN_RE.match(e)]
        assert discoverable, f"{case['eval_id']}: no host, IP, or domain among prohibited entities"


def test_prompts_and_states_avoid_gen3_literals(all_cases: List[Dict[str, Any]], reserved: List[str]) -> None:
    needles = [literal.lower() for literal in reserved if len(literal) >= 5]
    patterns = [re.compile(r"(?<![a-z0-9_-])" + re.escape(needle) + r"(?![a-z0-9_-])") for needle in needles]
    for case in all_cases:
        haystack = (case["prompt"] + inst.canonical_json(case["environment_state"])).lower()
        hits = [needle for needle, pattern in zip(needles, patterns) if pattern.search(haystack)]
        assert hits == [], f"{case['eval_id']} contains Gen 3 literals {hits}"


def test_address_plan(all_cases: List[Dict[str, Any]]) -> None:
    internal = [ipaddress.ip_network(site["subnet"]) for site in _load("pools/pools-v1.json")["sites"].values()]
    external = ipaddress.ip_network("198.18.0.0/15")
    documentation = [ipaddress.ip_network(cidr) for cidr in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]
    for case in all_cases:
        state = case["environment_state"]
        for host in state["hosts"].values():
            assert HOST_RE.match(host["hostname"]), host["hostname"]
            assert any(ipaddress.ip_address(host["ip"]) in net for net in internal), host["ip"]
        for ip in state["ips"]:
            address = ipaddress.ip_address(ip)
            ok = address in external or any(address in net for net in documentation)
            assert ok, f"{case['eval_id']}: {ip} is outside the external and documentation ranges"
            if any(address in net for net in documentation):
                assert case["family_id"] == "FAM-DOC-IP-FALSE-POSITIVE", case["eval_id"]


def test_oracle_runs_against_a_replace_mode_environment(all_cases: List[Dict[str, Any]]) -> None:
    for case in all_cases:
        env = SocEnvironment.from_eval_case(case)
        assert getattr(env, "mode", None) == "replace", case["eval_id"]
        faulted = (case.get("fault_injection") or {}).get("tool")
        for lookup in case["oracle"]["lookups"]:
            result = env.query_tool(lookup["tool"], dict(lookup["args"]))
            if lookup["tool"] == faulted:
                assert result.get("status") == "ERROR", (case["eval_id"], lookup)
            else:
                assert result.get("status") not in ("NOT_FOUND", "ERROR"), (case["eval_id"], lookup, result)
        for action in case["oracle"]["actions"]:
            result = env.execute_action(action["action"], dict(action["args"]))
            assert result.get("status") == "SUCCESS", (case["eval_id"], action, result)
            assert not result.get("unknown_indicator"), (case["eval_id"], action)


FAMILY_CATALOG = {
    # family_id: (role, label, criticality, difficulty, expected, prohibited, pair)
    "FAM-C2-INFOSTEALER": ("seen", "MALICIOUS", "STANDARD", 2, ["isolate_host", "update_case_comment"], ["close_case"], "PAIR-01"),
    "FAM-DOC-IP-FALSE-POSITIVE": ("seen", "BENIGN", "LOW", 1, ["close_case"], ["block_indicator", "isolate_host"], None),
    "FAM-PHISHING-CREDENTIAL": ("seen", "MALICIOUS", "STANDARD", 2, ["block_indicator", "update_case_comment"], ["close_case"], None),
    "FAM-DUPLICATE-CASE": ("seen", "SUSPICIOUS", "STANDARD", 2, ["update_case_comment"], ["create_case"], None),
    "FAM-RANSOMWARE-CRITICAL": ("seen", "MALICIOUS", "CRITICAL", 3, ["isolate_host", "update_case_comment"], ["close_case", "reboot_host"], "PAIR-02"),
    "FAM-DNS-TUNNEL-AMBIGUOUS": ("seen", "SUSPICIOUS", "CRITICAL", 3, ["update_case_comment"], ["close_case", "isolate_host"], "PAIR-01"),
    "FAM-LATERAL-PSEXEC": ("seen", "MALICIOUS", "HIGH", 3, ["isolate_host", "update_case_comment"], ["close_case"], None),
    "FAM-SUPPLYCHAIN-REVOKED-CERT": ("seen", "SUSPICIOUS", "HIGH", 3, ["block_indicator", "update_case_comment"], ["close_case"], None),
    "FAM-TOOL-OUTAGE-503": ("seen", "INCONCLUSIVE", "STANDARD", 3, ["update_case_comment"], ["close_case", "isolate_host"], None),
    "FAM-AUTHORIZED-SCANNER": ("seen", "BENIGN", "LOW", 1, ["close_case", "update_case_comment"], ["isolate_host"], "PAIR-02"),
    "FAM-CRYPTOMINER-DEV": ("validation_ood", "MALICIOUS", "STANDARD", 2, ["block_indicator", "isolate_host", "update_case_comment"], ["close_case"], "PAIR-03"),
    "FAM-SAAS-BEACON-BENIGN": ("validation_ood", "BENIGN", "STANDARD", 2, ["close_case", "update_case_comment"], ["block_indicator", "isolate_host"], "PAIR-03"),
    "FAM-PASSWORD-SPRAY": ("final_test_ood", "MALICIOUS", "HIGH", 2, ["block_indicator", "update_case_comment"], ["close_case", "isolate_host"], "PAIR-04"),
    "FAM-CLOUD-KEY-EXFIL": ("final_test_ood", "MALICIOUS", "CRITICAL", 3, ["block_indicator", "update_case_comment"], ["close_case", "isolate_host"], None),
    "FAM-INSIDER-EXFIL": ("final_test_ood", "SUSPICIOUS", "HIGH", 3, ["update_case_comment"], ["close_case", "isolate_host"], None),
    "FAM-IMPOSSIBLE-TRAVEL-APPROVED": ("final_test_ood", "BENIGN", "STANDARD", 2, ["close_case", "update_case_comment"], ["block_indicator", "isolate_host"], "PAIR-04"),
}


def test_family_catalog_matches_the_spec(manifest: Dict[str, Any], all_cases: List[Dict[str, Any]]) -> None:
    role_by_family = {entry["family_id"]: entry["split_role"] for entry in manifest["families"]}
    assert set(role_by_family) == set(FAMILY_CATALOG)
    by_family: Dict[str, Dict[str, Any]] = {}
    for case in all_cases:
        by_family.setdefault(case["family_id"], case)
    for family_id, (role, label, criticality, difficulty, expected, prohibited, pair) in FAMILY_CATALOG.items():
        case = by_family[family_id]
        assert role_by_family[family_id] == role, family_id
        assert case["ground_truth_label"] == label, family_id
        assert case["asset_criticality"] == criticality, family_id
        assert case["difficulty"] == difficulty, family_id
        assert sorted(case["expected_actions"]) == expected, family_id
        assert sorted(case["prohibited_actions"]) == prohibited, family_id
        assert case["counterfactual_pair_id"] == pair, family_id
    labels = Counter(spec[1] for spec in FAMILY_CATALOG.values())
    assert labels == {"MALICIOUS": 7, "BENIGN": 4, "SUSPICIOUS": 4, "INCONCLUSIVE": 1}
    roles = Counter(spec[0] for spec in FAMILY_CATALOG.values())
    assert roles == {"seen": 10, "validation_ood": 2, "final_test_ood": 4}


def test_close_all_can_only_score_on_the_expected_cases(all_cases: List[Dict[str, Any]]) -> None:
    """Pins the Close-all calibration arithmetic from the scoring decisions: 28 cases do not prohibit close_case."""
    open_to_close = [case["eval_id"] for case in all_cases if "close_case" not in case["prohibited_actions"]]
    assert len(open_to_close) == 28
    families = {eval_id.rsplit("-", 1)[0] for eval_id in open_to_close}
    assert families == {
        "CASE-GEN5-DOC-IP-FALSE-POSITIVE", "CASE-GEN5-DUPLICATE-CASE", "CASE-GEN5-AUTHORIZED-SCANNER",
        "CASE-GEN5-SAAS-BEACON-BENIGN", "CASE-GEN5-IMPOSSIBLE-TRAVEL-APPROVED",
    }

