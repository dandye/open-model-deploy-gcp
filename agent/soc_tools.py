"""Deterministic SOC inspection tools for Tier 1 alert triage and enrichment."""

import json

from typing import Any, Optional


def get_ip_address_report(ip: str) -> str:
    """Retrieves threat intelligence reputation and WHOIS context for an IP address.

    Args:
        ip: IPv4 or IPv6 address string.
    """
    clean_ip = str(ip).strip()
    if clean_ip == "10.0.99.50":
        return json.dumps({
            "ip": clean_ip,
            "category": "Internal Authorized Scanner",
            "reputation": "BENIGN_AUTHORIZED",
            "verdict": "SAFE",
            "service": "Qualys Vulnerability Scanner",
            "malicious_votes": 0,
            "harmless_votes": 100,
            "host_association": "SRV-PROD-PAYMENT-01",
            "asn": "RFC-1918 Private Subnet",
            "cidr": "10.0.99.0/24",
            "routing_status": "RFC-1918 (Non-Routable Private Subnet)",
            "vt_positives": 0,
            "vt_total": 72,
            "reverse_dns": "srv-prod-payment-01.corp.internal",
        })
    elif clean_ip.startswith("192.0.2.") or clean_ip.startswith("198.51.100.") or clean_ip.startswith("203.0.113."):
        if clean_ip == "198.51.100.42":
            return json.dumps({
                "ip": clean_ip,
                "category": "Known C2 Endpoint",
                "reputation": "MALICIOUS",
                "verdict": "MALICIOUS",
                "malicious_votes": 68,
                "harmless_votes": 0,
                "threat_family": "Lokibot / InfoStealer C2",
                "asn": "AS13335 (Malicious Hosting)",
                "cidr": "198.51.100.0/24",
                "routing_status": "Public Routable IP",
                "vt_positives": 68,
                "vt_total": 72,
                "reverse_dns": "update-service-win32.com",
            })
        rfc_num = "1" if clean_ip.startswith("192.0.2.") else ("2" if clean_ip.startswith("198.51.100.") else "3")
        cidr_prefix = "192.0.2.0/24" if clean_ip.startswith("192.0.2.") else ("198.51.100.0/24" if clean_ip.startswith("198.51.100.") else "203.0.113.0/24")
        return json.dumps({
            "ip": clean_ip,
            "category": "Documentation / Reserved RFC-5737",
            "reputation": "BENIGN / NON-ROUTABLE",
            "verdict": "SAFE",
            "malicious_votes": 0,
            "harmless_votes": 100,
            "asn": "AS0 (Documentation)",
            "cidr": cidr_prefix,
            "routing_status": f"RFC-5737 TEST-NET-{rfc_num} (Non-Routable Documentation Subnet)",
            "vt_positives": 0,
            "vt_total": 72,
            "reverse_dns": f"test-doc-{clean_ip.replace('.', '-')}.example.net",
        })
    elif clean_ip in ["10.0.4.15", "10.0.5.23", "10.0.8.99"]:
        host_name = "DESKTOP-HR-04" if clean_ip == "10.0.8.99" else "DESKTOP-FIN-08"
        return json.dumps({
            "ip": clean_ip,
            "category": "Internal Corporate Subnet",
            "reputation": "INTERNAL",
            "verdict": "NEUTRAL",
            "host_association": host_name,
            "asn": "RFC-1918 (Private Corporate Network)",
            "cidr": "10.0.0.0/16",
            "routing_status": "RFC-1918 (Non-Routable Private Subnet)",
            "vt_positives": 0,
            "vt_total": 72,
            "reverse_dns": f"{host_name.lower()}.corp.internal",
            "malicious_votes": 0,
            "harmless_votes": 100,
        })
    return json.dumps({
        "ip": clean_ip,
        "category": "Public IP",
        "reputation": "SUSPICIOUS",
        "verdict": "POTENTIALLY_MALICIOUS",
        "malicious_votes": 42,
        "harmless_votes": 2,
        "asn": "AS13335 (Public Transit)",
        "cidr": f"{clean_ip.rsplit('.', 1)[0]}.0/24",
        "routing_status": "Public Routable IP",
        "vt_positives": 42,
        "vt_total": 72,
        "reverse_dns": f"host-{clean_ip.replace('.', '-')}.isp-routing.net",
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
            "categories": ["Dynamic DNS / CDN Tunnel", "Content Delivery Network"],
            "reputation": "BORDERLINE_SUSPICIOUS",
            "malicious_votes": 18,
            "harmless_votes": 22,
            "vt_positives": 18,
            "vt_total": 72,
            "registrar": "Cloudflare, Inc.",
            "created_date": "2026-08-10",
            "threat_family": "None",
            "resolutions": ["203.0.113.15"],
            "passive_dns": ["203.0.113.15"],
        })
    elif domain_clean in ["update-service-win32.com", "evil.com", "malicious.com"]:
        return json.dumps({
            "domain": domain_clean,
            "verdict": "MALICIOUS",
            "category": "Lokibot / InfoStealer C2",
            "categories": ["Lokibot / InfoStealer C2", "Malware", "Command and Control"],
            "reputation": "MALICIOUS",
            "threat_family": "Lokibot / InfoStealer C2",
            "first_seen": "2026-07-01",
            "created_date": "2026-06-15",
            "registrar": "NameCheap, Inc." if domain_clean == "update-service-win32.com" else ("Tucows Domains Inc." if domain_clean == "evil.com" else "GoDaddy.com, LLC"),
            "malicious_votes": 68,
            "harmless_votes": 0,
            "vt_positives": 68,
            "vt_total": 72,
            "resolutions": ["198.51.100.42"],
            "passive_dns": ["198.51.100.42"],
        })
    return json.dumps({
        "domain": domain_clean,
        "verdict": "BENIGN",
        "category": "Uncategorized Domain",
        "categories": ["Search Engine", "Portal"] if domain_clean == "google.com" else ["Uncategorized Domain"],
        "reputation": "BENIGN",
        "threat_family": "None",
        "malicious_votes": 0,
        "harmless_votes": 100 if domain_clean == "google.com" else 95,
        "vt_positives": 0,
        "vt_total": 72,
        "registrar": "MarkMonitor Inc.",
        "created_date": "1997-09-15" if domain_clean == "google.com" else "2020-01-01",
        "resolutions": ["142.250.190.46"] if domain_clean == "google.com" else ["192.0.2.1"],
        "passive_dns": ["142.250.190.46"] if domain_clean == "google.com" else ["192.0.2.1"],
    })


def get_file_report(file_hash: str) -> str:
    """Retrieves file reputation, compilation time, and detection engines for a file hash.

    Args:
        file_hash: MD5, SHA-1, or SHA-256 hash string.
    """
    clean_hash = str(file_hash).strip()
    if clean_hash == "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90":
        return json.dumps({
            "hash": clean_hash,
            "hash_type": "SHA-256",
            "filename": "invoice_update.exe",
            "verdict": "SUSPICIOUS",
            "threat_name": "Signed.SupplyChain.Anomaly",
            "certificate_status": "REVOKED_BY_CA",
            "cert_status": "REVOKED_CERTIFICATE",
            "vendor": "Acme Corp (Compromised Signing Key)",
            "signer": "Acme Corp",
            "revocation_date": "2026-08-15",
            "vt_positives": 12,
            "vt_total": 72,
            "detections": "12/72 engines",
        })
    elif clean_hash == "275a50710b101da9773f64f4332e92719baa0ab607e034df1ca3bcf88f954f90":
        return json.dumps({
            "hash": clean_hash,
            "hash_type": "SHA-256",
            "filename": "trusted_tool.exe",
            "verdict": "BENIGN",
            "threat_name": "None",
            "certificate_status": "VALID",
            "cert_status": "VALID_CERTIFICATE",
            "vendor": "Microsoft Corporation",
            "signer": "Microsoft Corporation",
            "revocation_date": None,
            "vt_positives": 0,
            "vt_total": 72,
            "detections": "0/72 engines",
        })
    return json.dumps({
        "hash": clean_hash,
        "hash_type": "MD5" if len(clean_hash) == 32 else "SHA-256",
        "verdict": "MALICIOUS",
        "threat_name": "Trojan.Lokibot.Generic",
        "certificate_status": "UNSIGNED",
        "cert_status": "UNSIGNED",
        "vendor": "Unknown",
        "signer": "None",
        "revocation_date": None,
        "vt_positives": 54,
        "vt_total": 72,
        "detections": "54/72 engines",
    })


def lookup_entity(
    entity_id: str = "",
    entity_type: Optional[str] = "host",
    entity: str = "",
    **kwargs: Any,
) -> str:
    """Looks up SIEM telemetry and event history for a user, host, or IP.

    Args:
        entity_id: User email, hostname, or IP identifier.
        entity_type: Optional entity type classification ('host', 'user', 'ip').
        entity: Alternative keyword alias for entity_id.
        **kwargs: Additional keyword arguments.
    """
    raw_id = (
        entity_id
        or entity
        or kwargs.get("entity", "")
        or kwargs.get("target", "")
        or kwargs.get("id", "")
    )
    target_id = str(raw_id).strip()
    target_type = entity_type or "host"

    if target_id in ["DESKTOP-HR-04", "10.0.8.99"]:
        return json.dumps({
            "entity": target_id,
            "entity_type": target_type,
            "ip": "10.0.8.99",
            "criticality_tier": "HIGH",
            "active_user": "mwilson",
            "os": "Windows 10",
            "installed_services": ["WorkdayClient", "Office365", "PSEXESVC"],
            "siem_events_found": 28,
            "recent_event_types": ["VPN_AUTHENTICATION", "PROCESS_LAUNCH", "SMB_SESSION"],
            "process_command": "psexec.exe -u admin -p ... \\\\10.0.8.99 cmd.exe",
            "suspicious_indicators": True,
            "target_host": "10.0.8.99",
            "last_active": "2026-08-31T18:00:00Z",
            "source_ip": "10.0.8.99",
            "logon_type": "Type 3 Network Logon",
            "process_tree": [
                {
                    "pid": 1044,
                    "ppid": 420,
                    "process_name": "explorer.exe",
                    "command_line": "C:\\Windows\\explorer.exe",
                    "user": "mwilson",
                },
                {
                    "pid": 4820,
                    "ppid": 1044,
                    "process_name": "cmd.exe",
                    "command_line": "cmd.exe /c psexec.exe -u admin -p ... \\\\10.0.8.99 cmd.exe",
                    "user": "mwilson",
                },
                {
                    "pid": 5124,
                    "ppid": 4820,
                    "process_name": "PsExec.exe",
                    "command_line": "psexec.exe -u admin -p ... \\\\10.0.8.99 cmd.exe",
                    "user": "SYSTEM",
                },
            ],
            "events": [
                {
                    "timestamp": "2026-08-31T17:55:12Z",
                    "event_type": "VPN_AUTHENTICATION",
                    "user": "mwilson",
                    "source_ip": "198.51.100.42",
                    "status": "SUCCESS",
                },
                {
                    "timestamp": "2026-08-31T17:58:04Z",
                    "event_type": "SMB_SESSION",
                    "source_ip": "10.0.8.99",
                    "target_host": "10.0.8.99",
                    "share": "\\\\10.0.8.99\\ADMIN$",
                    "logon_type": "Type 3 Network Logon",
                },
                {
                    "timestamp": "2026-08-31T17:59:22Z",
                    "event_type": "PROCESS_LAUNCH",
                    "pid": 5124,
                    "process_name": "PsExec.exe",
                    "command_line": "psexec.exe -u admin -p ... \\\\10.0.8.99 cmd.exe",
                },
            ],
        })
    elif target_id in ["DESKTOP-FIN-08", "10.0.5.23"]:
        return json.dumps({
            "entity": target_id,
            "entity_type": target_type,
            "ip": "10.0.5.23",
            "criticality_tier": "HIGH",
            "active_user": "jdoe",
            "os": "Windows 10 Enterprise",
            "installed_services": ["AccountingApp", "Office365", "CrowdStrike"],
            "siem_events_found": 14,
            "recent_event_types": ["USER_LOGIN", "NETWORK_CONNECTION", "PROCESS_LAUNCH"],
            "suspicious_indicators": True,
            "last_active": "2026-08-31T18:00:00Z",
            "source_ip": "10.0.5.23",
            "logon_type": "Type 2 Interactive Logon",
            "process_tree": [
                {
                    "pid": 1100,
                    "ppid": 450,
                    "process_name": "explorer.exe",
                    "command_line": "C:\\Windows\\explorer.exe",
                    "user": "jdoe",
                },
                {
                    "pid": 2480,
                    "ppid": 1100,
                    "process_name": "powershell.exe",
                    "command_line": "powershell.exe -enc ...",
                    "user": "jdoe",
                },
            ],
            "events": [
                {
                    "timestamp": "2026-08-31T17:40:00Z",
                    "event_type": "USER_LOGIN",
                    "user": "jdoe",
                    "logon_type": "Type 2 Interactive Logon",
                    "source_ip": "10.0.5.23",
                },
                {
                    "timestamp": "2026-08-31T17:45:00Z",
                    "event_type": "NETWORK_CONNECTION",
                    "source_ip": "10.0.5.23",
                    "destination_ip": "198.51.100.42",
                    "destination_port": 443,
                },
            ],
        })
    return json.dumps({
        "entity": target_id,
        "entity_type": target_type,
        "siem_events_found": 14,
        "recent_event_types": ["USER_LOGIN", "NETWORK_CONNECTION", "PROCESS_LAUNCH"],
        "suspicious_indicators": True if ("evil" in target_id or "FIN" in target_id) else False,
        "last_active": "2026-08-25T14:30:00Z",
        "source_ip": "192.0.2.10",
        "logon_type": "Type 3 Network Logon" if "admin" in target_id else "Type 2 Interactive Logon",
        "process_tree": [
            {
                "pid": 1000,
                "ppid": 400,
                "process_name": "explorer.exe",
                "command_line": "C:\\Windows\\explorer.exe",
                "user": "system",
            }
        ],
        "events": [
            {
                "timestamp": "2026-08-25T14:25:00Z",
                "event_type": "NETWORK_CONNECTION",
                "source_ip": "192.0.2.10",
            }
        ],
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
