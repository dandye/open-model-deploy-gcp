"""Golden characterization of the Gen 3 SocEnvironment.

Recorded once, before the data-driven refactor, from commit 0ac24cd. Every
later change to agent/soc_environment.py must leave this test green. To
re-record (only when the frozen Gen 3 behavior is intentionally changed, which
the Gen 5 spec forbids), run:

    GEN3_GOLDEN_RECORD=1 .venv/bin/python -m pytest tests/test_gen3_soc_environment_parity.py -q
"""

import json
import os
from pathlib import Path

import pytest

from agent.soc_environment import SocEnvironment

GOLDEN_PATH = Path(__file__).parent / "golden" / "gen3_soc_environment_golden.json"

EXTRA_IPS = [
    "10.0.99.50", "198.51.100.42", "192.0.2.10", "203.0.113.7", "198.51.100.9",
    "10.0.4.15", "10.0.5.23", "10.0.8.99", "10.0.77.77", "172.16.3.4",
    "198.18.4.20", "8.8.8.8", "",
]
EXTRA_DOMAINS = ["error-503.service-unavailable.org", "unknown-domain.example", "EVIL.EXAMPLE", ""]
EXTRA_HASHES = ["a" * 64, "b" * 32, ""]
EXTRA_ENTITIES = ["DESKTOP-HR-04", "10.0.8.99", "evil-host", "WKS-FIN-99", "admin-box", "nobody", ""]
CASE_QUERIES = ["", "lokibot", "duplicate", "HIGH", "nothing-matches-this"]


def probe_calls(env: SocEnvironment):
    """Builds the ordered probe list from the environment's own inventory plus fixed extras."""
    calls = []
    host_ips = sorted({h.ip for h in env.hosts.values()})
    for ip in host_ips + EXTRA_IPS:
        calls.append(("query", "get_ip_address_report", {"ip": ip}))
    calls.append(("query", "get_ip_report", {"entity_id": "10.0.5.23"}))
    calls.append(("query", "get_ip_address_report", {"query": "198.51.100.42"}))
    for domain in sorted(env.domains) + EXTRA_DOMAINS:
        calls.append(("query", "get_domain_report", {"domain": domain}))
    calls.append(("query", "get_domain_report", {"query": "update-service-win32.com"}))
    for file_hash in sorted(env.hashes) + EXTRA_HASHES:
        calls.append(("query", "get_file_report", {"file_hash": file_hash}))
    calls.append(("query", "get_file_report", {"sha256": sorted(env.hashes)[0]}))
    for entity in sorted(env.hosts) + EXTRA_ENTITIES:
        calls.append(("query", "lookup_entity", {"entity_id": entity}))
        calls.append(("query", "summarize_entity", {"entity": entity, "entity_type": "host"}))
    for query in CASE_QUERIES:
        calls.append(("query", "list_cases", {"query": query}))
    for case_id in sorted(env.cases) + ["CASE-NOPE"]:
        calls.append(("query", "get_case", {"case_id": case_id}))
        calls.append(("query", "fetch_alert_data", {"siem_alert_id": f"alerts/{case_id}"}))
    calls.append(("query", "udm_search", {"query": 'principal.hostname = "DESKTOP-FIN-08"'}))
    calls.append(("query", "udm_search", {"query": ""}))
    calls.append(("query", "no_such_tool", {}))

    first_host = sorted(env.hosts)[0]
    first_case = sorted(env.cases)[0]
    first_domain = sorted(env.domains)[0]
    calls += [
        ("action", "isolate_host", {"hostname": first_host}),
        ("action", "isolate", {"ip": "10.0.0.250"}),
        ("action", "unisolate_host", {"hostname": first_host}),
        ("action", "unblock_host", {"hostname": "ghost"}),
        ("action", "block_indicator", {"indicator": first_domain}),
        ("action", "block_domain", {"domain": "evil.example"}),
        ("action", "block_ip", {"ip": "198.51.100.42"}),
        ("action", "block_hash", {}),
        ("action", "update_case_comment", {"case_id": first_case, "comment": "golden comment"}),
        ("action", "post_case_comment", {"caseId": f"cases/{first_case}", "text": "golden alias"}),
        ("action", "add_case_comment", {"case_id": "CASE-NOPE", "comment": "x"}),
        ("action", "close_case", {"case_id": first_case, "verdict": "BENIGN"}),
        ("action", "resolve_case", {"case_id": "CASE-NOPE"}),
        ("action", "reboot_host", {"hostname": first_host}),
        ("query", "get_case", {"case_id": first_case}),
        ("query", "lookup_entity", {"entity_id": first_host}),
        ("fault", "get_domain_report", {"status_code": 503, "error": "Service Unavailable"}),
        ("query", "get_domain_report", {"domain": first_domain}),
        ("clear_faults", "", {}),
        ("query", "get_domain_report", {"domain": first_domain}),
    ]
    return calls


def run_probes(env: SocEnvironment, calls):
    """Executes probes in order and returns a JSON-serializable transcript."""
    transcript = []
    for kind, name, args in calls:
        if kind == "query":
            result = env.query_tool(name, args)
        elif kind == "action":
            result = env.execute_action(name, args)
        elif kind == "fault":
            env.inject_fault(name, **args)
            result = {"fault_injected": name}
        elif kind == "clear_faults":
            env.clear_faults()
            result = {"faults_cleared": True}
        else:
            raise AssertionError(f"unknown probe kind {kind}")
        transcript.append({"kind": kind, "name": name, "args": args, "result": result})
    transcript.append({
        "kind": "final_state",
        "blocked_indicators": sorted(env.blocked_indicators),
        "isolated_hosts": sorted(name for name, host in env.hosts.items() if host.isolated),
        "case_states": {
            case_id: [case.status, case.stage, len(case.comments)]
            for case_id, case in sorted(env.cases.items())
        },
    })
    return transcript


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def test_gen3_environment_matches_golden():
    env = SocEnvironment()
    actual = run_probes(env, probe_calls(env))

    if os.environ.get("GEN3_GOLDEN_RECORD") == "1":
        GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN_PATH.write_text(json.dumps(actual, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        pytest.skip(f"golden recorded to {GOLDEN_PATH}")

    assert GOLDEN_PATH.exists(), "golden file missing; run once with GEN3_GOLDEN_RECORD=1"
    expected = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert len(actual) == len(expected), "probe count changed; the probe list is part of the contract"
    for index, (got, want) in enumerate(zip(actual, expected)):
        assert canonical(got) == canonical(want), (
            f"probe {index} ({want.get('kind')} {want.get('name')} {want.get('args')}) diverged from golden:\n"
            f"  want: {canonical(want)[:400]}\n  got:  {canonical(got)[:400]}"
        )


def test_golden_covers_every_default_entity():
    """Guards the probe list itself: every default entity must be probed at least once."""
    env = SocEnvironment()
    probed = canonical(probe_calls(env))
    for name in list(env.hosts) + list(env.domains) + list(env.hashes) + list(env.cases):
        assert name in probed, f"default entity {name} is not probed"
