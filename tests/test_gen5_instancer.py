"""Unit tests for scripts/gen5_instancer.py on an isolated temporary root."""

import hashlib
import ipaddress
import json
import re

import pytest

from agent.soc_environment import SocEnvironment
from gen5_fixtures import make_gen5_root, minimal_family
from scripts import gen5_instancer as gi

HOSTNAME_RE = re.compile(r"^[A-Z]{2,4}-[A-Z]{3}-[0-9]{2}$")


@pytest.fixture
def pools():
    return json.loads((gi.GEN5_ROOT / "pools" / "pools-v1.json").read_text(encoding="utf-8"))


def test_instance_seed_matches_spec_formula():
    expected = int(hashlib.sha256(b"pools-v1:FAM-TEST-MINIMAL:3").hexdigest()[:16], 16)
    assert gi.instance_seed("pools-v1", "FAM-TEST-MINIMAL", 3) == expected
    assert gi.instance_seed("pools-v1", "FAM-TEST-MINIMAL", 4) != expected
    assert gi.instance_seed("pools-v2", "FAM-TEST-MINIMAL", 3) != expected


def test_allocator_skips_reserved_and_used_values():
    allocator = gi.LiteralAllocator(["Taken-Host"])
    stream = iter(["taken-host", "fresh", "fresh", "other"])
    assert allocator.claim(lambda: next(stream)) == "fresh"
    assert allocator.claim(lambda: next(stream)) == "other"
    assert allocator.used == ["fresh", "other"]
    assert allocator.is_taken("FRESH") and allocator.is_taken("taken-host")
    with pytest.raises(gi.InstancerError, match="exhausted"):
        gi.LiteralAllocator(["same"]).claim(lambda: "same", attempts=5)


def test_slot_generators_produce_the_documented_formats(pools):
    family = minimal_family()
    family["slots"].update({
        "doc": {"type": "doc_ip"},
        "digest": {"type": "sha256"},
        "ticket": {"type": "ticket_id", "prefix": "TRV"},
        "key": {"type": "key_id"},
        "city": {"type": "choice", "pool": "travel_cities"},
        "city2": {"type": "choice", "pool": "travel_cities", "distinct_from": ["city"]},
    })
    seed = gi.instance_seed("pools-v1", family["family_id"], 0)
    values, meta = gi.render_slots(family, seed, pools, gi.LiteralAllocator([]))

    assert HOSTNAME_RE.match(values["host"]) and HOSTNAME_RE.match(values["other_host"])
    site = meta["host"]["site"]
    assert values["host"].split("-")[1] == site
    assert values["other_host"].split("-")[1] == site
    subnet = ipaddress.ip_network(pools["sites"][site]["subnet"])
    assert ipaddress.ip_address(values["host_ip"]) in subnet
    assert ipaddress.ip_address(values["other_ip"]) in subnet
    assert ipaddress.ip_address(values["bad_ip"]) in ipaddress.ip_network("198.18.0.0/15")
    assert any(ipaddress.ip_address(values["doc"]) in ipaddress.ip_network(c) for c in pools["doc_ip_cidrs"])
    assert re.fullmatch(r"[0-9a-f]{64}", values["digest"])
    assert re.fullmatch(r"[a-z]+\.[a-z]+", values["user"])
    assert re.fullmatch(r"CASE-[0-9]{5}", values["case_id"])
    assert re.fullmatch(r"TRV-[0-9]{5}", values["ticket"])
    assert re.fullmatch(r"CKEY-[0-9A-F]{16}", values["key"])
    assert re.fullmatch(r"2026-09-(0[1-9]|1[0-9]|2[0-8])T([01][0-9]|2[0-3]):[0-5][0-9]:00Z", values["when"])
    assert 2 <= int(values["count"]) <= 9
    assert values["flavor"] in pools["infostealer_families"]
    assert values["city"] in pools["travel_cities"] and values["city2"] != values["city"]
    assert re.fullmatch(r"[a-z]+[0-9]{2}\.(com|net|org|io|info|xyz)", values["bad_domain"])


def test_render_slots_is_deterministic(pools):
    family = minimal_family()
    seed = gi.instance_seed("pools-v1", family["family_id"], 1)
    first, _ = gi.render_slots(family, seed, pools, gi.LiteralAllocator([]))
    second, _ = gi.render_slots(family, seed, pools, gi.LiteralAllocator([]))
    assert first == second


def test_same_site_as_must_reference_an_earlier_host_or_ip_slot(pools):
    family = minimal_family()
    family["slots"] = {"ip_first": {"type": "internal_ip", "same_site_as": "host"}, **family["slots"]}
    with pytest.raises(gi.InstancerError, match="same_site_as"):
        gi.render_slots(family, 1, pools, gi.LiteralAllocator([]))


def test_unknown_slot_type_is_rejected(pools):
    family = minimal_family()
    family["slots"]["host"]["type"] = "mac_address"
    with pytest.raises(gi.InstancerError, match="unknown type"):
        gi.render_slots(family, 1, pools, gi.LiteralAllocator([]))


def test_render_value_rejects_unresolved_and_malformed_placeholders():
    with pytest.raises(gi.InstancerError, match="unresolved"):
        gi.render_value({"a": "{{nope}}"}, {})
    with pytest.raises(gi.InstancerError, match="malformed"):
        gi.render_value(["{{ x }}"], {"x": "1"})
    assert gi.render_value({"{{k}}": ["{{v}}", 3, True]}, {"k": "key", "v": "val"}) == {"key": ["val", 3, True]}


def test_build_case_renders_a_valid_replace_mode_world(pools):
    case, literals = gi.build_case(minimal_family(), pools, 0, gi.LiteralAllocator([]), "pools-v1")
    assert case["eval_id"] == "CASE-GEN5-TEST-MINIMAL-01"
    assert case["name"] == "Minimal test family [01]"
    assert case["generation"] == 5 and case["instance_index"] == 0 and case["pool_version"] == "pools-v1"
    assert case["template_sha256"] == gi.template_sha256(minimal_family())
    assert "{{" not in json.dumps(case)
    env = SocEnvironment.from_eval_case(case)
    assert env.mode == "replace"
    assert set(env.hosts) == set(case["environment_state"]["hosts"])
    assert len(literals) == 8
    text = json.dumps(case)
    assert all(literal in text for literal in literals)


def test_build_case_is_deterministic_across_fresh_allocators(pools):
    first, _ = gi.build_case(minimal_family(), pools, 2, gi.LiteralAllocator([]), "pools-v1")
    second, _ = gi.build_case(minimal_family(), pools, 2, gi.LiteralAllocator([]), "pools-v1")
    assert first == second


def test_allocator_redraws_on_collision(pools):
    first, _ = gi.build_case(minimal_family(), pools, 0, gi.LiteralAllocator([]), "pools-v1")
    host = next(iter(first["environment_state"]["hosts"]))
    second, _ = gi.build_case(minimal_family(), pools, 0, gi.LiteralAllocator([host]), "pools-v1")
    assert host not in second["environment_state"]["hosts"]


def _drop_distractor_from_prompt(family):
    family["prompt"] = family["prompt"].replace(
        "{{other_host}} ({{other_ip}}) on the same subnet showed nothing. ", ""
    )


def _extra_lookup(family):
    family["oracle"]["lookups"].append({"tool": "get_domain_report", "args": {"domain": "{{bad_domain}}"}})


@pytest.mark.parametrize(
    "mutate, message",
    [
        (_drop_distractor_from_prompt, "named in the prompt"),
        (lambda f: f["assertions"]["must_contain"].append("{{other_host}}"), "must_contain"),
        (lambda f: f["expected_actions"].append("isolate_host"), "expected actions"),
        (lambda f: f["oracle"]["actions"].append({"action": "close_case", "args": {"case_id": "{{case_id}}"}}), "prohibited action"),
        (lambda f: f["environment_state"]["hosts"]["{{host}}"].update({"bogus_field": 1}), "rejected by SocEnvironment"),
        (_extra_lookup, "repeats"),
        (lambda f: f["expected_entities"].append("ghost.example"), "not in environment_state"),
        (lambda f: f["oracle"]["actions"].insert(0, {"action": "isolate_host", "args": {"hostname": "{{other_host}}"}}), "prohibited entity"),
    ],
)
def test_build_case_rejects_contract_violations(pools, mutate, message):
    family = minimal_family()
    mutate(family)
    with pytest.raises(gi.InstancerError, match=message):
        gi.build_case(family, pools, 0, gi.LiteralAllocator([]), "pools-v1")


def test_collect_gen3_literals_covers_the_hard_coded_inventory():
    literals = gi.collect_gen3_literals()
    assert literals == sorted(literals)
    found = set(literals)
    for must in [
        "DESKTOP-FIN-08", "SRV-PROD-PAYMENT-01", "DESKTOP-HR-04", "VM-DEV-SANDBOX-12",
        "10.0.5.23", "10.0.99.50", "10.0.8.99", "10.0.4.15", "198.51.100.42", "192.0.2.10",
        "update-service-win32.com", "tunnel-data.cdn-edge-update.net", "error-503.service-unavailable.org",
        "CASE-33279", "CASE-17305", "jdoe", "svc_payment", "mwilson", "devuser",
    ]:
        assert must in found, must
    assert len(found) >= 40


def test_reserved_literals_file_is_current():
    path = gi.GEN5_ROOT / "pools" / "reserved_literals.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["literals"] == gi.collect_gen3_literals()


def test_build_check_show_and_literals_on_a_temporary_root(tmp_path, capsys):
    root = make_gen5_root(tmp_path)
    assert gi.main(["build", "--root", str(root)]) == 0
    for name in ["train.json", "validation.json", "final_test.json", "manifest.json"]:
        assert (root / name).exists(), name
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["splits"] == {
        "train": ["CASE-GEN5-TEST-MINIMAL-01"],
        "validation": ["CASE-GEN5-TEST-MINIMAL-02"],
        "final_test": [],
    }
    assert manifest["families"][0]["split_role"] == "seen"
    assert manifest["instancer_version"] == "1.0.0"
    assert manifest["evalset_id"] == "soc_tier1_families" and manifest["generation"] == 5
    expected_sha = hashlib.sha256(
        json.dumps(manifest["forbidden_literals"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert manifest["forbidden_literals_sha256"] == expected_sha
    assert manifest["supersedes"] == []
    train = json.loads((root / "train.json").read_text(encoding="utf-8"))
    assert train["split"] == "train" and train["evalset_id"] == "soc_tier1_families"
    case = train["eval_cases"][0]
    assert manifest["cases"][0]["case_sha256"] == gi.sha256_text(gi.canonical_json(case))
    assert set(manifest["cases"][0]["literals"]) <= set(manifest["forbidden_literals"])

    assert gi.main(["check", "--root", str(root)]) == 0
    assert gi.main(["build", "--root", str(root)]) == 0
    assert "up to date" in capsys.readouterr().out
    assert gi.main(["show", "CASE-GEN5-TEST-MINIMAL-02", "--root", str(root)]) == 0
    assert '"eval_id": "CASE-GEN5-TEST-MINIMAL-02"' in capsys.readouterr().out
    assert gi.main(["show", "CASE-GEN5-NOPE-01", "--root", str(root)]) == 1
    assert "CASE-GEN5-NOPE-01" in capsys.readouterr().err
    assert gi.main(["literals", "--root", str(root)]) == 0
    assert capsys.readouterr().out.splitlines() == manifest["forbidden_literals"]


def test_check_detects_template_drift_and_build_records_supersedes(tmp_path, capsys):
    root = make_gen5_root(tmp_path)
    assert gi.main(["build", "--root", str(root)]) == 0
    before = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    family_path = root / "families" / "FAM-TEST-MINIMAL.json"
    family = json.loads(family_path.read_text(encoding="utf-8"))
    family["prompt"] += " Treat with care."
    family_path.write_text(json.dumps(family, indent=2) + "\n", encoding="utf-8")

    assert gi.main(["check", "--root", str(root)]) == 1
    assert "DRIFT" in capsys.readouterr().out
    assert gi.main(["build", "--root", str(root)]) == 0
    after = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert sorted(after["supersedes"]) == sorted(c["case_sha256"] for c in before["cases"])
    assert after["families"][0]["template_sha256"] != before["families"][0]["template_sha256"]
    assert gi.main(["check", "--root", str(root)]) == 0


def test_check_detects_hand_edits_to_bundles(tmp_path):
    root = make_gen5_root(tmp_path)
    assert gi.main(["build", "--root", str(root)]) == 0
    path = root / "train.json"
    path.write_text(path.read_text(encoding="utf-8").replace("Investigate and respond.", "Investigate.", 1), encoding="utf-8")
    assert gi.main(["check", "--root", str(root)]) == 1


def test_split_plan_must_match_templates_on_disk(tmp_path):
    root = make_gen5_root(tmp_path)
    (root / "families" / "FAM-ORPHAN.json").write_text(json.dumps(minimal_family()) + "\n", encoding="utf-8")
    with pytest.raises(gi.InstancerError, match="split_plan"):
        gi.build_all(root)
