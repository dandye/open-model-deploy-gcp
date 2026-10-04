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
