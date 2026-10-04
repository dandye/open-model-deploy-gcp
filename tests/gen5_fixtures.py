"""Shared in-memory fixtures for the Gen 5 tests.

Importable as a plain module because pytest puts tests/ on sys.path for
test files that live in a directory without __init__.py.
"""

import json
import shutil
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
GEN5_ROOT = REPO_ROOT / "configs" / "evals" / "gen5"


def minimal_family() -> Dict[str, Any]:
    """A small but complete family template that exercises every slot relationship."""
    return {
        "family_id": "FAM-TEST-MINIMAL",
        "name": "Minimal test family",
        "ground_truth_label": "MALICIOUS",
        "asset_criticality": "STANDARD",
        "difficulty": 1,
        "counterfactual_pair_id": None,
        "transport": "sandbox",
        "slots": {
            "host": {"type": "hostname", "role": "workstation"},
            "host_ip": {"type": "internal_ip", "same_site_as": "host"},
            "user": {"type": "username", "owned_by": "host"},
            "other_host": {"type": "hostname", "role": "workstation", "same_site_as": "host"},
            "other_ip": {"type": "internal_ip", "same_site_as": "other_host"},
            "bad_domain": {"type": "domain", "style": "generic", "resolves_to": "bad_ip"},
            "bad_ip": {"type": "external_ip"},
            "case_id": {"type": "case_id"},
            "when": {"type": "timestamp"},
            "flavor": {"type": "choice", "pool": "infostealer_families"},
            "count": {"type": "integer", "min": 2, "max": 9},
        },
        "environment_state": {
            "mode": "replace",
            "hosts": {
                "{{host}}": {
                    "hostname": "{{host}}",
                    "ip": "{{host_ip}}",
                    "criticality_tier": "STANDARD",
                    "active_user": "{{user}}",
                    "telemetry": {
                        "siem_events_found": 1,
                        "recent_event_types": ["NETWORK_CONNECTION"],
                        "suspicious_indicators": True,
                        "events": [{"event_type": "NETWORK_CONNECTION", "destination_domain": "{{bad_domain}}"}],
                    },
                },
                "{{other_host}}": {"hostname": "{{other_host}}", "ip": "{{other_ip}}", "criticality_tier": "STANDARD"},
            },
            "ips": {
                "{{bad_ip}}": {
                    "ip": "{{bad_ip}}",
                    "reputation": "MALICIOUS",
                    "verdict": "MALICIOUS",
                    "category": "Known C2 Endpoint",
                    "malicious_votes": 40,
                    "harmless_votes": 0,
                }
            },
            "domains": {
                "{{bad_domain}}": {
                    "domain": "{{bad_domain}}",
                    "reputation": "MALICIOUS",
                    "verdict": "MALICIOUS",
                    "category": "Command and Control",
                    "malicious_votes": 42,
                    "harmless_votes": 0,
                    "threat_family": "{{flavor}}",
                    "resolutions": ["{{bad_ip}}"],
                    "passive_dns": ["{{bad_ip}}"],
                }
            },
            "hashes": {},
            "cases": {
                "{{case_id}}": {
                    "case_id": "{{case_id}}",
                    "title": "Beacon from {{host}} to {{bad_domain}}",
                    "priority": "MEDIUM",
                    "stage": "TRIAGE",
                    "status": "OPEN",
                    "assignee": "soc-queue",
                }
            },
            "events": [
                {
                    "event_timestamp": "{{when}}",
                    "metadata": {"event_type": "NETWORK_CONNECTION"},
                    "principal": {"hostname": "{{host}}", "ip": "{{host_ip}}"},
                    "target": {"hostname": "{{bad_domain}}", "ip": "{{bad_ip}}"},
                }
            ],
        },
        "prompt": (
            "Alert {{case_id}}: {{host}} ({{host_ip}}, user {{user}}) connected {{count}} times to "
            "{{bad_domain}} since {{when}}. {{other_host}} ({{other_ip}}) on the same subnet showed "
            "nothing. Investigate and respond."
        ),
        "expected_actions": ["block_indicator", "update_case_comment"],
        "prohibited_actions": ["close_case"],
        "expected_entities": ["{{bad_domain}}", "{{host}}"],
        "prohibited_entities": ["{{other_host}}"],
        "cmdb_context": {
            "asset_id": "{{host}}",
            "owner": "{{user}}",
            "business_role": "Standard workstation",
            "criticality": "STANDARD",
            "blast_radius": "Single user",
        },
        "reference": {
            "expected_verdict": "MALICIOUS",
            "expected_threat_family": "{{flavor}}",
            "recommended_action": "Block {{bad_domain}} and document the finding in {{case_id}}.",
            "grading_rubric": (
                "Full credit for blocking {{bad_domain}} after confirming its reputation and leaving "
                "{{other_host}} alone; no credit for closing the case."
            ),
        },
        "assertions": {"must_contain": ["{{bad_domain}}"], "must_not_contain": ["false positive"]},
        "fault_injection": None,
        "liveness": {"min_epistemic_steps": 1},
        "oracle": {
            "lookups": [
                {"tool": "get_domain_report", "args": {"domain": "{{bad_domain}}"}},
                {"tool": "lookup_entity", "args": {"entity_id": "{{host}}"}},
            ],
            "actions": [
                {"action": "block_indicator", "args": {"indicator": "{{bad_domain}}"}},
                {
                    "action": "update_case_comment",
                    "args": {
                        "case_id": "{{case_id}}",
                        "comment": "Confirmed {{flavor}} C2 at {{bad_domain}} from {{host}}; indicator blocked, case left open.",
                    },
                },
            ],
        },
    }


def minimal_split_plan() -> Dict[str, Any]:
    """Two instances of the minimal family: index 0 in train, index 1 in validation."""
    return {
        "pool_version": "pools-v1",
        "roles": {
            "seen": {"instances": 2, "splits": {"train": [0], "validation": [1]}},
            "validation_ood": {"instances": 1, "splits": {"validation": [0]}},
            "final_test_ood": {"instances": 1, "splits": {"final_test": [0]}},
        },
        "families": {"FAM-TEST-MINIMAL": {"role": "seen", "instances": 2}},
    }


def make_gen5_root(tmp_path: Path, families=None, split_plan=None) -> Path:
    """Builds a self-contained Gen 5 root in tmp_path using the real pools and schemas."""
    root = tmp_path / "gen5"
    (root / "families").mkdir(parents=True)
    (root / "pools").mkdir()
    shutil.copytree(GEN5_ROOT / "schema", root / "schema")
    shutil.copy(GEN5_ROOT / "pools" / "pools-v1.json", root / "pools" / "pools-v1.json")
    reserved_src = GEN5_ROOT / "pools" / "reserved_literals.json"
    if reserved_src.exists():
        shutil.copy(reserved_src, root / "pools" / "reserved_literals.json")
    else:
        (root / "pools" / "reserved_literals.json").write_text(json.dumps({"literals": []}) + "\n")
    for family in families or [minimal_family()]:
        (root / "families" / f"{family['family_id']}.json").write_text(json.dumps(family, indent=2) + "\n")
    (root / "split_plan.json").write_text(json.dumps(split_plan or minimal_split_plan(), indent=2) + "\n")
    return root
