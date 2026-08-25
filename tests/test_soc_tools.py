"""Unit tests for deterministic SOC inspection tools."""

import json
from agent.soc_tools import (
    get_domain_report,
    get_file_report,
    get_ip_address_report,
    list_cases,
    lookup_entity,
    post_case_comment,
)


def test_ip_report_rfc5737():
    """Verify RFC-5737 documentation IPs return benign verdict."""
    for ip in ["192.0.2.100", "198.51.100.5", "203.0.113.42"]:
        raw = get_ip_address_report(ip)
        data = json.loads(raw)
        assert data["ip"] == ip
        assert data["verdict"] == "SAFE"
        assert "RFC-5737" in data["category"]
        assert data["malicious_votes"] == 0


def test_ip_report_internal():
    """Verify internal corporate IPs return internal categorization."""
    for ip in ["10.0.4.15", "10.0.5.23"]:
        raw = get_ip_address_report(ip)
        data = json.loads(raw)
        assert data["ip"] == ip
        assert data["verdict"] == "NEUTRAL"
        assert data["category"] == "Internal Corporate Subnet"
        assert "host_association" in data


def test_ip_report_public():
    """Verify arbitrary public IPs return suspicious default."""
    raw = get_ip_address_report("1.1.1.1")
    data = json.loads(raw)
    assert data["ip"] == "1.1.1.1"
    assert data["verdict"] == "POTENTIALLY_MALICIOUS"
    assert data["malicious_votes"] == 42


def test_domain_report_malicious():
    """Verify known malicious domains return malicious verdict."""
    for domain in ["update-service-win32.com", "evil.com", "malicious.com"]:
        raw = get_domain_report(domain)
        data = json.loads(raw)
        assert data["domain"] == domain
        assert data["verdict"] == "MALICIOUS"
        assert "Lokibot" in data["threat_family"]
        assert data["malicious_votes"] == 68


def test_domain_report_benign():
    """Verify unknown/benign domains return benign verdict."""
    raw = get_domain_report("google.com")
    data = json.loads(raw)
    assert data["domain"] == "google.com"
    assert data["verdict"] == "BENIGN"
    assert data["threat_family"] == "None"


def test_file_report():
    """Verify file report parsing for MD5 and SHA-256."""
    md5_hash = "d41d8cd98f00b204e9800998ecf8427e"
    raw_md5 = get_file_report(md5_hash)
    data_md5 = json.loads(raw_md5)
    assert data_md5["hash"] == md5_hash
    assert data_md5["hash_type"] == "MD5"
    assert data_md5["verdict"] == "MALICIOUS"

    sha256_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    raw_sha = get_file_report(sha256_hash)
    data_sha = json.loads(raw_sha)
    assert data_sha["hash"] == sha256_hash
    assert data_sha["hash_type"] == "SHA-256"
    assert data_sha["verdict"] == "MALICIOUS"


def test_lookup_entity():
    """Verify SIEM telemetry lookup for users and hosts."""
    raw_user = lookup_entity("john.doe@company.com")
    data_user = json.loads(raw_user)
    assert data_user["entity"] == "john.doe@company.com"
    assert data_user["siem_events_found"] == 14
    assert data_user["suspicious_indicators"] is False

    raw_host = lookup_entity("DESKTOP-FIN-08")
    data_host = json.loads(raw_host)
    assert data_host["entity"] == "DESKTOP-FIN-08"
    assert data_host["suspicious_indicators"] is True


def test_list_cases():
    """Verify SOAR case search query returns expected cases."""
    raw_hit = list_cases("198.51.100.42")
    data_hit = json.loads(raw_hit)
    assert len(data_hit["cases"]) == 1
    assert data_hit["cases"][0]["case_id"] == "CASE-33279"

    raw_miss = list_cases("nonexistent-search")
    data_miss = json.loads(raw_miss)
    assert len(data_miss["cases"]) == 0
    assert data_miss["total"] == 0


def test_post_case_comment():
    """Verify posting comment to SOAR case."""
    comment = "Triage completed: Host isolated and escalated to Tier 2."
    raw = post_case_comment("CASE-33279", comment)
    data = json.loads(raw)
    assert data["status"] == "SUCCESS"
    assert data["case_id"] == "CASE-33279"
    assert data["bytes_posted"] == len(comment)
