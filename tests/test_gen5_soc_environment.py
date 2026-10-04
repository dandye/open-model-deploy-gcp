"""Replace-mode (Gen 5) behavior of SocEnvironment.

Overlay mode is covered by tests/test_gen3_soc_environment.py and the golden
parity test; this file only covers what Gen 5 adds.
"""

from copy import deepcopy

import pytest

from agent.soc_environment import HostEntity, IpIndicatorEntity, SocEnvironment


def replace_state():
    """A minimal self-contained world in the exact shape Plan 2's instancer emits."""
    return {
        "mode": "replace",
        "hosts": {
            "WKS-AUS-17": {
                "hostname": "WKS-AUS-17",
                "ip": "10.7.0.17",
                "criticality_tier": "STANDARD",
                "active_user": "mara.okafor",
                "telemetry": {
                    "siem_events_found": 3,
                    "recent_event_types": ["NETWORK_CONNECTION", "PROCESS_LAUNCH"],
                    "suspicious_indicators": True,
                    "events": [{"event_type": "NETWORK_CONNECTION", "destination_ip": "198.18.4.20"}],
                },
            },
            "WKS-AUS-22": {
                "hostname": "WKS-AUS-22",
                "ip": "10.7.0.22",
                "criticality_tier": "STANDARD",
                "active_user": "theo.lindqvist",
            },
        },
        "ips": {
            "198.18.4.20": {
                "ip": "198.18.4.20",
                "reputation": "MALICIOUS",
                "verdict": "MALICIOUS",
                "category": "Known C2 Endpoint",
                "asn": "AS64500 (Bulletproof Hosting)",
                "cidr": "198.18.4.0/24",
                "routing_status": "Public Routable IP",
                "threat_family": "Vidar / InfoStealer C2",
                "malicious_votes": 61,
                "harmless_votes": 0,
                "vt_positives": 61,
                "vt_total": 72,
                "reverse_dns": "cdn-sync-metrics41.com",
            }
        },
        "domains": {
            "cdn-sync-metrics41.com": {
                "domain": "cdn-sync-metrics41.com",
                "reputation": "MALICIOUS",
                "verdict": "MALICIOUS",
                "category": "Command and Control",
                "malicious_votes": 61,
                "harmless_votes": 0,
                "threat_family": "Vidar / InfoStealer C2",
                "resolutions": ["198.18.4.20"],
            }
        },
        "hashes": {},
        "cases": {
            "CASE-40417": {
                "case_id": "CASE-40417",
                "title": "Beacon from WKS-AUS-17 to cdn-sync-metrics41.com",
                "priority": "MEDIUM",
                "stage": "TRIAGE",
                "status": "OPEN",
                "assignee": "soc-queue",
            }
        },
        "events": [
            {
                "event_timestamp": "2026-10-01T09:14:00Z",
                "metadata": {"event_type": "NETWORK_CONNECTION"},
                "principal": {"hostname": "WKS-AUS-17", "ip": "10.7.0.17"},
                "target": {"hostname": "cdn-sync-metrics41.com", "ip": "198.18.4.20"},
            }
        ],
    }


def test_replace_mode_starts_empty_and_loads_only_the_given_world():
    env = SocEnvironment(initial_state=replace_state())
    assert env.mode == "replace"
    assert env.strict is True
    assert set(env.hosts) == {"WKS-AUS-17", "WKS-AUS-22"}
    assert "DESKTOP-FIN-08" not in env.hosts
    assert set(env.domains) == {"cdn-sync-metrics41.com"}
    assert "update-service-win32.com" not in env.domains
    assert env.hashes == {}
    assert set(env.cases) == {"CASE-40417"}
    assert set(env.ips) == {"198.18.4.20"}
    assert isinstance(env.ips["198.18.4.20"], IpIndicatorEntity)
    assert env.ips["198.18.4.20"].threat_family == "Vidar / InfoStealer C2"
    assert len(env.events) == 1


def test_overlay_mode_is_the_default_and_carries_the_gen3_ip_specials():
    env = SocEnvironment()
    assert env.mode == "overlay"
    assert env.strict is False
    assert "DESKTOP-FIN-08" in env.hosts
    assert set(env.ips) == {"10.0.99.50", "198.51.100.42"}
    assert env.events == []
    assert env.hosts["DESKTOP-FIN-08"].telemetry == {}


def test_overlay_state_without_mode_still_overlays():
    env = SocEnvironment(initial_state={"hosts": {"WKS-AUS-17": {"hostname": "WKS-AUS-17", "ip": "10.7.0.17", "criticality_tier": "LOW"}}})
    assert env.mode == "overlay"
    assert "WKS-AUS-17" in env.hosts
    assert "DESKTOP-FIN-08" in env.hosts


def test_invalid_mode_is_rejected():
    with pytest.raises(ValueError, match="mode"):
        SocEnvironment(initial_state={"mode": "merge"})


def test_host_telemetry_is_loaded_and_defaults_to_empty():
    env = SocEnvironment(initial_state=replace_state())
    assert env.hosts["WKS-AUS-17"].telemetry["suspicious_indicators"] is True
    assert env.hosts["WKS-AUS-22"].telemetry == {}
    assert HostEntity(hostname="X", ip="10.0.0.1", criticality_tier="LOW").telemetry == {}


def test_ip_indicator_to_report_omits_empty_optional_fields_and_merges_extra():
    minimal = IpIndicatorEntity(ip="198.18.9.9")
    report = minimal.to_report()
    assert report["ip"] == "198.18.9.9"
    assert report["reputation"] == "NO_DATA"
    assert report["verdict"] == "UNKNOWN"
    assert report["cidr"] == "198.18.9.0/24"
    for absent in ("threat_family", "service", "host_association", "country"):
        assert absent not in report
    rich = IpIndicatorEntity(ip="198.18.9.9", threat_family="Vidar", service="svc", host_association="H", country="NL", extra={"criticality_tier": "HIGH"})
    rich_report = rich.to_report()
    assert rich_report["threat_family"] == "Vidar"
    assert rich_report["service"] == "svc"
    assert rich_report["host_association"] == "H"
    assert rich_report["country"] == "NL"
    assert rich_report["criticality_tier"] == "HIGH"


def test_snapshot_and_reset_roundtrip_in_replace_mode():
    env = SocEnvironment(initial_state=replace_state())
    env.execute_action("isolate_host", {"hostname": "WKS-AUS-17"})
    env.execute_action("block_indicator", {"indicator": "cdn-sync-metrics41.com"})
    snapshot = env.get_state_snapshot()
    assert snapshot["mode"] == "replace"
    assert snapshot["ips"]["198.18.4.20"]["reputation"] == "MALICIOUS"
    assert snapshot["events"] == replace_state()["events"]
    assert snapshot["hosts"]["WKS-AUS-17"]["isolated"] is True
    assert snapshot["hosts"]["WKS-AUS-17"]["telemetry"]["siem_events_found"] == 3

    restored = SocEnvironment(initial_state=deepcopy(snapshot))
    assert restored.mode == "replace"
    assert set(restored.hosts) == {"WKS-AUS-17", "WKS-AUS-22"}
    assert restored.hosts["WKS-AUS-17"].isolated is True
    assert restored.blocked_indicators == {"cdn-sync-metrics41.com"}
    assert "DESKTOP-FIN-08" not in restored.hosts

    env.reset()
    assert env.mode == "replace"
    assert env.hosts["WKS-AUS-17"].isolated is False
    assert env.blocked_indicators == set()
    assert "DESKTOP-FIN-08" not in env.hosts


def test_from_eval_case_uses_environment_state_in_replace_mode():
    case = {"eval_id": "CASE-GEN5-C2-INFOSTEALER-01", "generation": 5, "environment_state": replace_state()}
    env = SocEnvironment.from_eval_case(case)
    assert env.mode == "replace"
    assert set(env.hosts) == {"WKS-AUS-17", "WKS-AUS-22"}
    assert env.faults == {}


def test_from_eval_case_applies_fault_on_top_of_environment_state():
    case = {
        "eval_id": "CASE-GEN5-TOOL-OUTAGE-503-01",
        "generation": 5,
        "environment_state": replace_state(),
        "fault_injection": {"tool": "get_domain_report", "status_code": 503, "error": "Upstream TI unavailable"},
    }
    env = SocEnvironment.from_eval_case(case)
    assert env.mode == "replace"
    assert env.query_tool("get_domain_report", {"domain": "cdn-sync-metrics41.com"}) == {
        "error": "Upstream TI unavailable",
        "status_code": 503,
        "status": "ERROR",
    }


def test_from_eval_case_rejects_gen5_case_without_environment_state():
    with pytest.raises(ValueError, match="environment_state"):
        SocEnvironment.from_eval_case({"eval_id": "CASE-GEN5-X-01", "generation": 5})


def test_from_eval_case_keeps_gen3_overlay_behavior():
    env = SocEnvironment.from_eval_case({"eval_id": "CASE-GEN3-01-LOKIBOT-C2"})
    assert env.mode == "overlay"
    assert "DESKTOP-FIN-08" in env.hosts
    faulted = SocEnvironment.from_eval_case({"eval_id": "CASE-GEN3-09", "fault_injection": {"tool": "get_domain_report"}})
    assert faulted.faults == {"get_domain_report": {"status_code": 503, "error": "Service Unavailable"}}


def test_from_eval_case_rejects_non_object_environment_state():
    with pytest.raises(ValueError, match="environment_state"):
        SocEnvironment.from_eval_case({"eval_id": "X", "generation": 5, "environment_state": ["not", "a", "dict"]})


def test_strict_ip_report_inventory_hit_renders_the_entity():
    env = SocEnvironment(initial_state=replace_state())
    report = env.query_tool("get_ip_address_report", {"ip": "198.18.4.20"})
    assert report["reputation"] == "MALICIOUS"
    assert report["threat_family"] == "Vidar / InfoStealer C2"
    assert report["reverse_dns"] == "cdn-sync-metrics41.com"
    assert report["cidr"] == "198.18.4.0/24"


def test_strict_ip_report_for_a_host_ip_is_internal_with_association():
    env = SocEnvironment(initial_state=replace_state())
    report = env.query_tool("get_ip_report", {"entity_id": "10.7.0.17"})
    assert report["reputation"] == "INTERNAL"
    assert report["verdict"] == "NEUTRAL"
    assert report["host_association"] == "WKS-AUS-17"
    assert report["criticality_tier"] == "STANDARD"
    assert report["reverse_dns"] == "wks-aus-17.corp.internal"
    assert report["harmless_votes"] == 0


def test_strict_ip_report_for_rfc5737_is_documentation_with_zero_votes():
    env = SocEnvironment(initial_state=replace_state())
    report = env.query_tool("get_ip_address_report", {"ip": "203.0.113.7"})
    assert report["category"] == "Documentation / Reserved RFC-5737"
    assert report["routing_status"] == "RFC-5737 TEST-NET-3 (Non-Routable Documentation Subnet)"
    assert report["verdict"] == "SAFE"
    assert report["harmless_votes"] == 0
    assert report["cidr"] == "203.0.113.0/24"


def test_strict_ip_report_for_unknown_rfc1918_is_internal_unknown():
    env = SocEnvironment(initial_state=replace_state())
    for ip in ("10.200.1.1", "172.16.3.4", "192.168.50.5"):
        report = env.query_tool("get_ip_address_report", {"ip": ip})
        assert report["reputation"] == "INTERNAL", ip
        assert report["host_association"] == "Unknown", ip


def test_strict_ip_report_for_unknown_external_is_no_data_not_suspicious():
    env = SocEnvironment(initial_state=replace_state())
    for ip in ("198.18.9.9", "8.8.8.8", "1.1.1.1"):
        report = env.query_tool("get_ip_address_report", {"ip": ip})
        assert report["reputation"] == "NO_DATA", ip
        assert report["verdict"] == "UNKNOWN", ip
        assert report["malicious_votes"] == 0, ip
        assert "threat_family" not in report, ip


def test_strict_ip_report_does_not_carry_the_gen3_lokibot_special_case():
    env = SocEnvironment(initial_state=replace_state())
    report = env.query_tool("get_ip_address_report", {"ip": "198.51.100.42"})
    assert report["reputation"] != "MALICIOUS"
    assert report["malicious_votes"] == 0
    assert "threat_family" not in report
    assert report["routing_status"] == "RFC-5737 TEST-NET-2 (Non-Routable Documentation Subnet)"


def test_overlay_ip_report_keeps_legacy_fallbacks():
    env = SocEnvironment()
    assert env.query_tool("get_ip_address_report", {"ip": "8.8.8.8"})["reputation"] == "SUSPICIOUS"
    assert env.query_tool("get_ip_address_report", {"ip": "198.51.100.42"})["threat_family"] == "Lokibot / InfoStealer C2"
    assert env.query_tool("get_ip_address_report", {"ip": "10.0.99.50"})["service"] == "Qualys Vulnerability Scanner"


def test_strict_domain_report_inventory_hit_and_unknown():
    env = SocEnvironment(initial_state=replace_state())
    hit = env.query_tool("get_domain_report", {"domain": "CDN-Sync-Metrics41.com"})
    assert hit["verdict"] == "MALICIOUS"
    assert hit["resolutions"] == ["198.18.4.20"]
    miss = env.query_tool("get_domain_report", {"domain": "updates.vendor-portal.example"})
    assert miss["reputation"] == "NO_DATA"
    assert miss["verdict"] == "UNKNOWN"
    assert miss["resolutions"] == []
    assert miss["passive_dns"] == []
    assert miss["registrar"] == "Unknown"
    assert miss["created_date"] is None


def test_strict_domain_report_has_no_hardcoded_503_domain():
    env = SocEnvironment(initial_state=replace_state())
    report = env.query_tool("get_domain_report", {"domain": "error-503.service-unavailable.org"})
    assert "error" not in report
    assert report["reputation"] == "NO_DATA"


def test_overlay_domain_report_keeps_hardcoded_503_and_benign_default():
    env = SocEnvironment()
    assert env.query_tool("get_domain_report", {"domain": "error-503.service-unavailable.org"})["status_code"] == 503
    assert env.query_tool("get_domain_report", {"domain": "unknown-domain.example"})["verdict"] == "BENIGN"


def test_strict_file_report_unknown_hash_is_not_fabricated_malware():
    env = SocEnvironment(initial_state=replace_state())
    report = env.query_tool("get_file_report", {"file_hash": "c" * 64})
    assert report["verdict"] == "UNKNOWN"
    assert report["status"] == "NOT_FOUND"
    assert report["threat_name"] == "None"
    assert report["detections"] == "0/0 engines"
    assert report["hash_type"] == "SHA-256"
    md5 = env.query_tool("get_file_report", {"hash": "d" * 32})
    assert md5["hash_type"] == "MD5"


def test_overlay_file_report_keeps_lokibot_default():
    env = SocEnvironment()
    assert env.query_tool("get_file_report", {"file_hash": "c" * 64})["threat_name"] == "Trojan.Lokibot.Generic"



