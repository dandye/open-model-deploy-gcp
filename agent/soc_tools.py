"""Deterministic SOC inspection tools for Tier 1 alert triage and enrichment."""

import json


def get_ip_address_report(ip: str) -> str:
    """Retrieves threat intelligence reputation and WHOIS context for an IP address.

    Args:
        ip: IPv4 or IPv6 address string.
    """
    if ip == "10.0.99.50":
        return json.dumps({
            "ip": ip,
            "category": "Internal Authorized Scanner",
            "reputation": "BENIGN_AUTHORIZED",
            "verdict": "SAFE",
            "service": "Qualys Vulnerability Scanner",
            "malicious_votes": 0,
            "harmless_votes": 100,
        })
    elif ip.startswith("192.0.2.") or ip.startswith("198.51.100.") or ip.startswith("203.0.113."):
        return json.dumps({
            "ip": ip,
            "category": "Documentation / Reserved RFC-5737",
            "reputation": "BENIGN / NON-ROUTABLE",
            "verdict": "SAFE",
            "malicious_votes": 0,
            "harmless_votes": 100,
            "asn": "AS0 (Documentation)",
        })
    elif ip == "10.0.4.15" or ip == "10.0.5.23":
        return json.dumps({
            "ip": ip,
            "category": "Internal Corporate Subnet",
            "reputation": "INTERNAL",
            "verdict": "NEUTRAL",
            "host_association": "DESKTOP-FIN-08",
        })
    return json.dumps({
        "ip": ip,
        "category": "Public IP",
        "reputation": "SUSPICIOUS",
        "verdict": "POTENTIALLY_MALICIOUS",
        "malicious_votes": 42,
        "harmless_votes": 2,
    })


def get_domain_report(domain: str) -> str:
    """Retrieves GTI threat intelligence verdict and passive DNS for a domain.

    Args:
        domain: Domain FQDN string (e.g. 'evil.com', 'google.com').
    """
    domain_clean = domain.strip().lower()
    if domain_clean == "error-503.service-unavailable.org":
        return json.dumps({
            "error": "HTTP 503: Upstream Threat Intelligence Service Unavailable",
            "status_code": 503,
            "domain": domain_clean,
        })
    elif domain_clean == "tunnel-data.cdn-edge-update.net":
        return json.dumps({
            "domain": domain_clean,
            "verdict": "BORDERLINE_SUSPICIOUS",
            "category": "Dynamic DNS / CDN Tunnel",
            "malicious_votes": 18,
            "harmless_votes": 22,
        })
    elif domain_clean in ["update-service-win32.com", "evil.com", "malicious.com"]:
        return json.dumps({
            "domain": domain_clean,
            "verdict": "MALICIOUS",
            "threat_family": "Lokibot / InfoStealer C2",
            "first_seen": "2026-07-01",
            "malicious_votes": 68,
            "harmless_votes": 0,
            "resolutions": ["198.51.100.42"],
        })
    return json.dumps({
        "domain": domain_clean,
        "verdict": "BENIGN",
        "threat_family": "None",
        "malicious_votes": 0,
        "harmless_votes": 95,
    })


def get_file_report(file_hash: str) -> str:
    """Retrieves file reputation, compilation time, and detection engines for a file hash.

    Args:
        file_hash: MD5, SHA-1, or SHA-256 hash string.
    """
    if file_hash == "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90":
        return json.dumps({
            "hash": file_hash,
            "hash_type": "SHA-256",
            "verdict": "SUSPICIOUS",
            "threat_name": "Signed.SupplyChain.Anomaly",
            "certificate_status": "REVOKED_CERTIFICATE",
            "vendor": "Acme Corp (Compromised Signing Key)",
            "detections": "12/72 engines",
        })
    return json.dumps({
        "hash": file_hash,
        "hash_type": "MD5" if len(file_hash) == 32 else "SHA-256",
        "verdict": "MALICIOUS",
        "threat_name": "Trojan.Lokibot.Generic",
        "detections": "54/72 engines",
    })


def lookup_entity(entity_id: str) -> str:
    """Looks up SIEM telemetry and event history for a user, host, or IP.

    Args:
        entity_id: User email, hostname, or IP identifier.
    """
    if entity_id in ["DESKTOP-HR-04", "10.0.8.99"]:
        return json.dumps({
            "entity": entity_id,
            "siem_events_found": 28,
            "recent_event_types": ["VPN_AUTHENTICATION", "PROCESS_LAUNCH", "SMB_SESSION"],
            "process_command": "psexec.exe -u admin -p ... \\\\10.0.8.99 cmd.exe",
            "suspicious_indicators": True,
            "target_host": "10.0.8.99",
            "last_active": "2026-08-31T18:00:00Z",
        })
    return json.dumps({
        "entity": entity_id,
        "siem_events_found": 14,
        "recent_event_types": ["USER_LOGIN", "NETWORK_CONNECTION", "PROCESS_LAUNCH"],
        "suspicious_indicators": True if "evil" in entity_id or "FIN" in entity_id else False,
        "last_active": "2026-08-25T14:30:00Z",
    })


def list_cases(query: str) -> str:
    """Queries open SOAR cases matching the search terms.

    Args:
        query: Search string (e.g. IP address, hostname, case ID).
    """
    if "198.51.100.42" in query or "33279" in query:
        return json.dumps({
            "cases": [
                {
                    "case_id": "CASE-33279",
                    "title": "Suspected Lokibot C2 Beaconing",
                    "priority": "HIGH",
                    "status": "OPEN",
                    "assigned_to": "Tier 1 Queue",
                }
            ]
        })
    return json.dumps({"cases": [], "total": 0})


def post_case_comment(case_id: str, comment: str) -> str:
    """Posts an investigative update or triage note to an existing SOAR case.

    Args:
        case_id: Target SOAR Case ID.
        comment: Plain text triage summary and recommendations.
    """
    return json.dumps({"status": "SUCCESS", "case_id": case_id, "bytes_posted": len(comment)})
