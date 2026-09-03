"""Unit tests for the Gen 3 Interactive SOC Sandbox & Dynamic State Machine."""

import pytest
from agent.soc_environment import (
    CaseEntity,
    DomainEntity,
    HashEntity,
    HostEntity,
    SocEnvironment,
)


def test_soc_environment_initialization():
    """Verifies that default entities and state structures are populated on initialization."""
    env = SocEnvironment()
    assert len(env.hosts) >= 4
    assert len(env.domains) >= 4
    assert len(env.hashes) >= 3
    assert len(env.cases) >= 2

    # Check specific default hosts
    assert "DESKTOP-FIN-08" in env.hosts
    fin_host = env.hosts["DESKTOP-FIN-08"]
    assert isinstance(fin_host, HostEntity)
    assert fin_host.ip == "10.0.5.23"
    assert fin_host.criticality_tier == "HIGH"
    assert fin_host.isolated is False

    # Check payment server
    assert "SRV-PROD-PAYMENT-01" in env.hosts
    payment_host = env.hosts["SRV-PROD-PAYMENT-01"]
    assert payment_host.criticality_tier == "CRITICAL"
    assert payment_host.ip == "10.0.99.50"

    # Check domain entity
    assert "update-service-win32.com" in env.domains
    domain = env.domains["update-service-win32.com"]
    assert isinstance(domain, DomainEntity)
    assert domain.verdict == "MALICIOUS"
    assert domain.malicious_votes > 0

    # Check hash entity
    sha = "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"
    assert sha in env.hashes
    hash_ent = env.hashes[sha]
    assert isinstance(hash_ent, HashEntity)
    assert hash_ent.cert_status == "REVOKED_CERTIFICATE"

    # Check case entity
    assert "CASE-33279" in env.cases
    case_ent = env.cases["CASE-33279"]
    assert isinstance(case_ent, CaseEntity)
    assert case_ent.priority == "HIGH"
    assert case_ent.status == "OPEN"


def test_soc_environment_custom_initial_state():
    """Verifies initialization with custom initial state dictionary."""
    custom_state = {
        "hosts": {
            "CUSTOM-SRV-01": {
                "hostname": "CUSTOM-SRV-01",
                "ip": "172.16.0.10",
                "criticality_tier": "CRITICAL",
                "isolated": False,
                "os": "Linux RHEL 9",
                "active_user": "root",
                "installed_services": ["CustomDB"],
            }
        },
        "domains": {
            "custom-evil.org": {
                "domain": "custom-evil.org",
                "reputation": "MALICIOUS",
                "verdict": "MALICIOUS",
                "category": "C2",
                "malicious_votes": 50,
                "harmless_votes": 0,
            }
        },
    }
    env = SocEnvironment(initial_state=custom_state)
    assert "CUSTOM-SRV-01" in env.hosts
    assert env.hosts["CUSTOM-SRV-01"].ip == "172.16.0.10"
    assert "custom-evil.org" in env.domains


def test_query_tool_epistemic_queries():
    """Verifies epistemic tool queries for IP, domain, hash, entity, and cases."""
    env = SocEnvironment()

    # Query IP report
    ip_res = env.query_tool("get_ip_address_report", {"ip": "10.0.99.50"})
    assert ip_res["ip"] == "10.0.99.50"
    assert ip_res["verdict"] == "SAFE"

    # Query domain report
    dom_res = env.query_tool("get_domain_report", {"domain": "update-service-win32.com"})
    assert dom_res["verdict"] == "MALICIOUS"
    assert dom_res["domain"] == "update-service-win32.com"

    # Query file report
    hash_val = "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"
    file_res = env.query_tool("get_file_report", {"file_hash": hash_val})
    assert file_res["certificate_status"] in ["REVOKED_CERTIFICATE", "REVOKED_BY_CA"]
    assert file_res["verdict"] == "SUSPICIOUS"

    # Query entity lookup
    ent_res = env.query_tool("lookup_entity", {"entity_id": "DESKTOP-HR-04"})
    assert ent_res["entity"] == "DESKTOP-HR-04"
    assert ent_res["suspicious_indicators"] is True

    # Query list cases
    cases_res = env.query_tool("list_cases", {"query": "33279"})
    assert len(cases_res["cases"]) == 1
    assert cases_res["cases"][0]["case_id"] == "CASE-33279"

    # Query get case
    case_res = env.query_tool("get_case", {"case_id": "CASE-33279"})
    assert case_res["case_id"] == "CASE-33279"
    assert case_res["priority"] == "HIGH"


def test_execute_action_host_isolation_and_unblock():
    """Verifies host isolation and unblocking state transitions."""
    env = SocEnvironment()
    assert env.hosts["DESKTOP-FIN-08"].isolated is False

    # Isolate host by hostname
    iso_res = env.execute_action("isolate_host", {"hostname": "DESKTOP-FIN-08"})
    assert iso_res["status"] == "SUCCESS"
    assert iso_res["isolated"] is True
    assert env.hosts["DESKTOP-FIN-08"].isolated is True

    # Isolate host by IP
    iso_ip_res = env.execute_action("isolate_host", {"ip": "10.0.8.99"})
    assert iso_ip_res["status"] == "SUCCESS"
    assert env.hosts["DESKTOP-HR-04"].isolated is True

    # Unblock host
    unblock_res = env.execute_action("unblock_host", {"hostname": "DESKTOP-FIN-08"})
    assert unblock_res["status"] == "SUCCESS"
    assert unblock_res["isolated"] is False
    assert env.hosts["DESKTOP-FIN-08"].isolated is False


def test_execute_action_block_indicator():
    """Verifies indicator blocking action."""
    env = SocEnvironment()
    res = env.execute_action("block_indicator", {"indicator": "update-service-win32.com"})
    assert res["status"] == "SUCCESS"
    assert "update-service-win32.com" in env.blocked_indicators


def test_execute_action_case_comment_and_close():
    """Verifies posting comments and closing cases."""
    env = SocEnvironment()
    comment_text = "Investigated host DESKTOP-FIN-08. Confirmed Lokibot C2 beaconing."
    res = env.execute_action("update_case_comment", {
        "case_id": "CASE-33279",
        "comment": comment_text,
    })
    assert res["status"] == "SUCCESS"
    assert comment_text in env.cases["CASE-33279"].comments

    # Close case
    close_res = env.execute_action("close_case", {
        "case_id": "CASE-33279",
        "verdict": "TRUE_POSITIVE_CONTAINED",
    })
    assert close_res["status"] == "SUCCESS"
    assert env.cases["CASE-33279"].status == "CLOSED"
    assert env.cases["CASE-33279"].stage == "RESOLVED"


def test_fault_injection_and_recovery():
    """Verifies simulating upstream service degradation and clearing faults."""
    env = SocEnvironment()

    # Query before fault injection
    dom_res = env.query_tool("get_domain_report", {"domain": "update-service-win32.com"})
    assert "error" not in dom_res

    # Inject HTTP 503 fault
    env.inject_fault("get_domain_report", status_code=503, error="Upstream Threat Intel 503 Unavailable")
    fault_res = env.query_tool("get_domain_report", {"domain": "update-service-win32.com"})
    assert fault_res["status_code"] == 503
    assert "Upstream Threat Intel 503 Unavailable" in fault_res["error"]

    # Clear faults and verify normal query returns
    env.clear_faults()
    recovered_res = env.query_tool("get_domain_report", {"domain": "update-service-win32.com"})
    assert recovered_res["verdict"] == "MALICIOUS"
    assert "error" not in recovered_res


def test_state_snapshot_and_reset():
    """Verifies state serialization snapshot and full state reset."""
    env = SocEnvironment()

    # Make multiple state modifications
    env.execute_action("isolate_host", {"hostname": "DESKTOP-FIN-08"})
    env.execute_action("block_indicator", {"indicator": "evil.com"})
    env.execute_action("update_case_comment", {"case_id": "CASE-33279", "comment": "Note 1"})
    env.inject_fault("lookup_entity", status_code=500, error="Internal SIEM Error")

    snapshot = env.get_state_snapshot()
    assert snapshot["hosts"]["DESKTOP-FIN-08"]["isolated"] is True
    assert "evil.com" in snapshot["blocked_indicators"]
    assert len(snapshot["action_history"]) == 3
    assert "lookup_entity" in snapshot["faults"]

    # Reset environment
    env.reset()
    assert env.hosts["DESKTOP-FIN-08"].isolated is False
    assert len(env.blocked_indicators) == 0
    assert len(env.action_history) == 0
    assert len(env.faults) == 0
    assert "Note 1" not in env.cases["CASE-33279"].comments


def test_enriched_domain_telemetry():
    """Verifies enriched domain telemetry fields in soc_environment and soc_tools."""
    from agent.soc_tools import get_domain_report as tools_get_domain_report
    import json

    env = SocEnvironment()

    # Query malicious C2 domain
    res_env = env.query_tool("get_domain_report", {"domain": "update-service-win32.com"})
    assert res_env["domain"] == "update-service-win32.com"
    assert res_env["verdict"] == "MALICIOUS"
    assert "registrar" in res_env
    assert "created_date" in res_env
    assert res_env["vt_positives"] == 68
    assert res_env["vt_total"] == 72
    assert "categories" in res_env
    assert isinstance(res_env["categories"], list)
    assert "passive_dns" in res_env
    assert "198.51.100.42" in res_env["passive_dns"]
    assert "Lokibot" in res_env["threat_family"]

    # Test soc_tools version
    raw_tools = tools_get_domain_report("update-service-win32.com")
    res_tools = json.loads(raw_tools)
    assert res_tools["registrar"] == res_env["registrar"]
    assert res_tools["vt_positives"] == 68
    assert res_tools["vt_total"] == 72
    assert "passive_dns" in res_tools


def test_enriched_ip_telemetry():
    """Verifies enriched IP telemetry with RFC-5737 and routable classifications."""
    from agent.soc_tools import get_ip_address_report as tools_get_ip_report
    import json

    env = SocEnvironment()

    # 1. RFC-5737 TEST-NET-1 IP
    res_rfc = env.query_tool("get_ip_address_report", {"ip": "192.0.2.100"})
    assert res_rfc["ip"] == "192.0.2.100"
    assert res_rfc["verdict"] == "SAFE"
    assert res_rfc["routing_status"] == "RFC-5737 TEST-NET-1 (Non-Routable Documentation Subnet)"
    assert res_rfc["cidr"] == "192.0.2.0/24"
    assert "asn" in res_rfc
    assert res_rfc["vt_positives"] == 0
    assert res_rfc["vt_total"] == 72
    assert "reverse_dns" in res_rfc

    # Test soc_tools RFC-5737
    raw_tools_rfc = tools_get_ip_report("192.0.2.100")
    res_tools_rfc = json.loads(raw_tools_rfc)
    assert res_tools_rfc["routing_status"] == "RFC-5737 TEST-NET-1 (Non-Routable Documentation Subnet)"
    assert res_tools_rfc["vt_positives"] == 0

    # 2. Public routable C2 IP
    res_c2 = env.query_tool("get_ip_address_report", {"ip": "198.51.100.42"})
    assert res_c2["ip"] == "198.51.100.42"
    assert res_c2["verdict"] == "MALICIOUS"
    assert res_c2["routing_status"] == "Public Routable IP"
    assert res_c2["vt_positives"] == 68
    assert res_c2["vt_total"] == 72

    # 3. Authorized scanner IP
    res_scan = env.query_tool("get_ip_address_report", {"ip": "10.0.99.50"})
    assert res_scan["verdict"] == "SAFE"
    assert res_scan["vt_positives"] == 0
    assert "RFC-1918" in res_scan["routing_status"]


def test_enriched_file_telemetry():
    """Verifies enriched file telemetry including signer, certificate status, and VT ratios."""
    from agent.soc_tools import get_file_report as tools_get_file_report
    import json

    env = SocEnvironment()

    sha = "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"
    res_env = env.query_tool("get_file_report", {"file_hash": sha})
    assert res_env["signer"] == "Acme Corp"
    assert res_env["certificate_status"] == "REVOKED_BY_CA"
    assert res_env["revocation_date"] == "2026-08-15"
    assert res_env["vt_positives"] == 12
    assert res_env["vt_total"] == 72
    assert res_env["verdict"] == "SUSPICIOUS"

    # Test soc_tools version
    raw_tools = tools_get_file_report(sha)
    res_tools = json.loads(raw_tools)
    assert res_tools["signer"] == "Acme Corp"
    assert res_tools["certificate_status"] == "REVOKED_BY_CA"
    assert res_tools["revocation_date"] == "2026-08-15"
    assert res_tools["vt_positives"] == 12


def test_enriched_entity_telemetry():
    """Verifies process tree, logon type, source IP, and events in entity lookup."""
    from agent.soc_tools import lookup_entity as tools_lookup_entity
    import json

    env = SocEnvironment()

    # Lateral movement host
    res_env = env.query_tool("lookup_entity", {"entity_id": "DESKTOP-HR-04", "entity_type": "host"})
    assert res_env["entity"] == "DESKTOP-HR-04"
    assert res_env["logon_type"] == "Type 3 Network Logon"
    assert "source_ip" in res_env
    assert "process_tree" in res_env
    assert len(res_env["process_tree"]) >= 3
    assert any("psexec" in str(p.get("command_line", "")).lower() for p in res_env["process_tree"])
    assert "events" in res_env
    assert len(res_env["events"]) >= 3

    # Test soc_tools version
    raw_tools = tools_lookup_entity("DESKTOP-HR-04")
    res_tools = json.loads(raw_tools)
    assert res_tools["logon_type"] == "Type 3 Network Logon"
    assert len(res_tools["process_tree"]) >= 3
    assert len(res_tools["events"]) >= 3

