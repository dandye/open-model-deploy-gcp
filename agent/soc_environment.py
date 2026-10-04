"""Interactive SOC Sandbox and Dynamic State Machine for Agentic Evaluation.

Maintains live entity state (hosts, domains, hashes, cases), supports epistemic
tool queries, pragmatic state-changing interventions, upstream fault injection,
and full state snapshotting/restoration.
"""

from copy import deepcopy
from dataclasses import asdict, dataclass, field
import datetime
import ipaddress
import json
from typing import Any, Dict, List, Optional, Set

_RFC5737_PREFIXES = ("192.0.2.", "198.51.100.", "203.0.113.")
_RFC1918_NETWORKS = (
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
)


def _is_rfc1918(ip: str) -> bool:
    """True only for the three RFC 1918 blocks (not for TEST-NET or benchmarking space)."""
    try:
        address = ipaddress.IPv4Address(ip)
    except (ipaddress.AddressValueError, ValueError):
        return False
    return any(address in network for network in _RFC1918_NETWORKS)


def _slash24(ip: str) -> str:
    return f"{ip.rsplit('.', 1)[0]}.0/24" if ip.count(".") == 3 else ""


@dataclass
class HostEntity:
    """Represents a managed host/workstation entity in the enterprise asset inventory."""

    hostname: str
    ip: str
    criticality_tier: str  # 'LOW', 'STANDARD', 'HIGH', 'CRITICAL'
    isolated: bool = False
    os: str = "Windows 10"
    active_user: str = "jdoe"
    installed_services: List[str] = field(default_factory=list)
    telemetry: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DomainEntity:
    """Represents a domain indicator and threat intelligence reputation profile."""

    domain: str
    reputation: str
    verdict: str
    category: str
    malicious_votes: int = 0
    harmless_votes: int = 0
    threat_family: str = "None"
    resolutions: List[str] = field(default_factory=list)
    first_seen: Optional[str] = None
    registrar: str = "Unknown Registrar"
    created_date: Optional[str] = None
    vt_positives: int = 0
    vt_total: int = 72
    categories: List[str] = field(default_factory=list)
    passive_dns: List[str] = field(default_factory=list)


@dataclass
class HashEntity:
    """Represents a file hash indicator and binary telemetry record."""

    sha256: str
    filename: str
    cert_status: str  # 'VALID_CERTIFICATE', 'REVOKED_CERTIFICATE', 'UNSIGNED'
    vendor: str
    threat_name: str
    verdict: str
    detections: str = "0/72 engines"
    signer: str = "Unknown"
    certificate_status: str = "VALID"
    revocation_date: Optional[str] = None
    vt_positives: int = 0
    vt_total: int = 72


@dataclass
class CaseEntity:
    """Represents a SOAR incident case record and investigation history."""

    case_id: str
    title: str
    priority: str  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    stage: str  # 'TRIAGE', 'INVESTIGATION', 'CONTAINMENT', 'RESOLVED'
    status: str  # 'OPEN', 'IN_PROGRESS', 'CLOSED'
    assignee: str
    comments: List[str] = field(default_factory=list)


@dataclass
class IpIndicatorEntity:
    """Represents an IP address indicator and its threat intelligence profile.

    Unknown IPs are never fabricated: an entity exists only when a world
    declares it. Optional descriptive fields are omitted from reports when
    empty so that overlay-mode reports keep their historical key sets.
    """

    ip: str
    reputation: str = "NO_DATA"
    verdict: str = "UNKNOWN"
    category: str = "Public IP"
    asn: str = "Unknown"
    cidr: str = ""
    routing_status: str = "Public Routable IP"
    threat_family: str = "None"
    malicious_votes: int = 0
    harmless_votes: int = 0
    vt_positives: int = 0
    vt_total: int = 72
    reverse_dns: str = ""
    service: str = ""
    host_association: str = ""
    country: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_report(self) -> Dict[str, Any]:
        """Renders the report dictionary returned by get_ip_address_report."""
        cidr = self.cidr or (f"{self.ip.rsplit('.', 1)[0]}.0/24" if self.ip.count(".") == 3 else "")
        report: Dict[str, Any] = {
            "ip": self.ip,
            "category": self.category,
            "reputation": self.reputation,
            "verdict": self.verdict,
            "malicious_votes": self.malicious_votes,
            "harmless_votes": self.harmless_votes,
            "asn": self.asn,
            "cidr": cidr,
            "routing_status": self.routing_status,
            "vt_positives": self.vt_positives,
            "vt_total": self.vt_total,
            "reverse_dns": self.reverse_dns,
        }
        if self.threat_family and self.threat_family != "None":
            report["threat_family"] = self.threat_family
        if self.service:
            report["service"] = self.service
        if self.host_association:
            report["host_association"] = self.host_association
        if self.country:
            report["country"] = self.country
        report.update(deepcopy(self.extra))
        return report


@dataclass
class EnvironmentAction:
    """Represents a recorded state-changing action executed within the environment."""

    action_name: str
    arguments: Dict[str, Any]
    timestamp: str
    status: str
    result: Dict[str, Any] = field(default_factory=dict)


def _get_default_hosts() -> Dict[str, HostEntity]:
    """Generates default realistic enterprise host inventory."""
    return {
        "DESKTOP-FIN-08": HostEntity(
            hostname="DESKTOP-FIN-08",
            ip="10.0.5.23",
            criticality_tier="HIGH",
            isolated=False,
            os="Windows 10 Enterprise",
            active_user="jdoe",
            installed_services=["AccountingApp", "Office365", "CrowdStrike"],
        ),
        "SRV-PROD-PAYMENT-01": HostEntity(
            hostname="SRV-PROD-PAYMENT-01",
            ip="10.0.99.50",
            criticality_tier="CRITICAL",
            isolated=False,
            os="Ubuntu 22.04 LTS",
            active_user="svc_payment",
            installed_services=["PaymentGateway", "Qualys Scanner", "SSH"],
        ),
        "DESKTOP-HR-04": HostEntity(
            hostname="DESKTOP-HR-04",
            ip="10.0.8.99",
            criticality_tier="STANDARD",
            isolated=False,
            os="Windows 10",
            active_user="mwilson",
            installed_services=["WorkdayClient", "Office365"],
        ),
        "VM-DEV-SANDBOX-12": HostEntity(
            hostname="VM-DEV-SANDBOX-12",
            ip="10.0.4.15",
            criticality_tier="LOW",
            isolated=False,
            os="Debian 12",
            active_user="devuser",
            installed_services=["Docker", "Python3", "Git"],
        ),
    }


def _get_default_domains() -> Dict[str, DomainEntity]:
    """Generates default threat intelligence domain profiles."""
    return {
        "update-service-win32.com": DomainEntity(
            domain="update-service-win32.com",
            reputation="MALICIOUS",
            verdict="MALICIOUS",
            category="Lokibot / InfoStealer C2",
            malicious_votes=68,
            harmless_votes=0,
            threat_family="Lokibot / InfoStealer C2",
            resolutions=["198.51.100.42"],
            first_seen="2026-07-01",
            registrar="NameCheap, Inc.",
            created_date="2026-06-15",
            vt_positives=68,
            vt_total=72,
            categories=["Lokibot / InfoStealer C2", "Malware", "Command and Control"],
            passive_dns=["198.51.100.42"],
        ),
        "tunnel-data.cdn-edge-update.net": DomainEntity(
            domain="tunnel-data.cdn-edge-update.net",
            reputation="BORDERLINE_SUSPICIOUS",
            verdict="BORDERLINE_SUSPICIOUS",
            category="Dynamic DNS / CDN Tunnel",
            malicious_votes=18,
            harmless_votes=22,
            threat_family="None",
            resolutions=["203.0.113.15"],
            first_seen="2026-08-01",
            registrar="Cloudflare, Inc.",
            created_date="2026-08-10",
            vt_positives=18,
            vt_total=72,
            categories=["Dynamic DNS / CDN Tunnel", "Content Delivery Network"],
            passive_dns=["203.0.113.15"],
        ),
        "evil.com": DomainEntity(
            domain="evil.com",
            reputation="MALICIOUS",
            verdict="MALICIOUS",
            category="C2 Infrastructure",
            malicious_votes=68,
            harmless_votes=0,
            threat_family="Lokibot / InfoStealer C2",
            resolutions=["198.51.100.42"],
            first_seen="2025-11-20",
            registrar="Tucows Domains Inc.",
            created_date="2025-11-20",
            vt_positives=68,
            vt_total=72,
            categories=["C2 Infrastructure", "Phishing", "Malware"],
            passive_dns=["198.51.100.42"],
        ),
        "malicious.com": DomainEntity(
            domain="malicious.com",
            reputation="MALICIOUS",
            verdict="MALICIOUS",
            category="Phishing",
            malicious_votes=68,
            harmless_votes=1,
            threat_family="Lokibot / InfoStealer C2",
            resolutions=["198.51.100.99"],
            first_seen="2026-01-05",
            registrar="GoDaddy.com, LLC",
            created_date="2026-01-05",
            vt_positives=68,
            vt_total=72,
            categories=["Phishing", "Credential Harvesting"],
            passive_dns=["198.51.100.99"],
        ),
        "google.com": DomainEntity(
            domain="google.com",
            reputation="BENIGN",
            verdict="BENIGN",
            category="Search Engine",
            malicious_votes=0,
            harmless_votes=100,
            threat_family="None",
            resolutions=["142.250.190.46"],
            first_seen="1997-09-15",
            registrar="MarkMonitor Inc.",
            created_date="1997-09-15",
            vt_positives=0,
            vt_total=72,
            categories=["Search Engine", "Portal"],
            passive_dns=["142.250.190.46"],
        ),
        "error-503.service-unavailable.org": DomainEntity(
            domain="error-503.service-unavailable.org",
            reputation="UNKNOWN",
            verdict="ERROR",
            category="Fault Simulation",
            malicious_votes=0,
            harmless_votes=0,
            threat_family="None",
        ),
    }


def _get_default_hashes() -> Dict[str, HashEntity]:
    """Generates default file hash records."""
    return {
        "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90": HashEntity(
            sha256="a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90",
            filename="invoice_update.exe",
            cert_status="REVOKED_CERTIFICATE",
            vendor="Acme Corp (Compromised Signing Key)",
            threat_name="Signed.SupplyChain.Anomaly",
            verdict="SUSPICIOUS",
            detections="12/72 engines",
            signer="Acme Corp",
            certificate_status="REVOKED_BY_CA",
            revocation_date="2026-08-15",
            vt_positives=12,
            vt_total=72,
        ),
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855": HashEntity(
            sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            filename="payload_dropper.bin",
            cert_status="UNSIGNED",
            vendor="Unknown",
            threat_name="Trojan.Lokibot.Generic",
            verdict="MALICIOUS",
            detections="54/72 engines",
            signer="None",
            certificate_status="UNSIGNED",
            revocation_date=None,
            vt_positives=54,
            vt_total=72,
        ),
        "275a50710b101da9773f64f4332e92719baa0ab607e034df1ca3bcf88f954f90": HashEntity(
            sha256="275a50710b101da9773f64f4332e92719baa0ab607e034df1ca3bcf88f954f90",
            filename="trusted_tool.exe",
            cert_status="VALID_CERTIFICATE",
            vendor="Microsoft Corporation",
            threat_name="None",
            verdict="BENIGN",
            detections="0/72 engines",
            signer="Microsoft Corporation",
            certificate_status="VALID",
            revocation_date=None,
            vt_positives=0,
            vt_total=72,
        ),
    }


def _get_default_cases() -> Dict[str, CaseEntity]:
    """Generates default SOAR case inventory."""
    return {
        "CASE-33279": CaseEntity(
            case_id="CASE-33279",
            title="Suspected Lokibot C2 Beaconing",
            priority="HIGH",
            stage="TRIAGE",
            status="OPEN",
            assignee="Tier 1 Queue",
            comments=["Automated SIEM alert ingested from DESKTOP-FIN-08 beaconing to update-service-win32.com"],
        ),
        "CASE-17305": CaseEntity(
            case_id="CASE-17305",
            title="Anomalous Internal Admin Port Scan",
            priority="CRITICAL",
            stage="TRIAGE",
            status="OPEN",
            assignee="Tier 1 Queue",
            comments=["Qualys vulnerability scan detected on SRV-PROD-PAYMENT-01"],
        ),
    }


def _get_default_ips() -> Dict[str, IpIndicatorEntity]:
    """The two IP indicators Gen 3 special-cased in code, now carried as data."""
    return {
        "10.0.99.50": IpIndicatorEntity(
            ip="10.0.99.50",
            reputation="BENIGN_AUTHORIZED",
            verdict="SAFE",
            category="Internal Authorized Scanner",
            asn="RFC-1918 Private Subnet",
            cidr="10.0.99.0/24",
            routing_status="RFC-1918 (Non-Routable Private Subnet)",
            malicious_votes=0,
            harmless_votes=100,
            vt_positives=0,
            vt_total=72,
            reverse_dns="srv-prod-payment-01.corp.internal",
            service="Qualys Vulnerability Scanner",
            host_association="SRV-PROD-PAYMENT-01",
        ),
        "198.51.100.42": IpIndicatorEntity(
            ip="198.51.100.42",
            reputation="MALICIOUS",
            verdict="MALICIOUS",
            category="Known C2 Endpoint",
            asn="AS13335 (Malicious Hosting)",
            cidr="198.51.100.0/24",
            routing_status="Public Routable IP",
            threat_family="Lokibot / InfoStealer C2",
            malicious_votes=68,
            harmless_votes=0,
            vt_positives=68,
            vt_total=72,
            reverse_dns="update-service-win32.com",
        ),
    }


class SocEnvironment:
    """Interactive SOC Sandbox and Dynamic State Machine for Agentic Evaluations."""

    def __init__(self, initial_state: Optional[Dict[str, Any]] = None):
        """Initializes SOC environment with default or custom entity configurations."""
        self._initial_state_config = deepcopy(initial_state) if initial_state else None
        self.hosts: Dict[str, HostEntity] = {}
        self.domains: Dict[str, DomainEntity] = {}
        self.hashes: Dict[str, HashEntity] = {}
        self.cases: Dict[str, CaseEntity] = {}
        self.ips: Dict[str, IpIndicatorEntity] = {}
        self.events: List[Dict[str, Any]] = []
        self.mode: str = "overlay"
        self.blocked_indicators: Set[str] = set()
        self.action_history: List[EnvironmentAction] = []
        self.faults: Dict[str, Dict[str, Any]] = {}

        self._load_state(self._initial_state_config)

    @property
    def strict(self) -> bool:
        """True in replace mode: respond only from data, never synthesize."""
        return self.mode == "replace"

    @classmethod
    def from_eval_case(cls, case: Dict[str, Any]) -> "SocEnvironment":
        """Create an isolated case environment from its declared world and tool fault.

        Gen 5 cases carry a full ``environment_state`` (``mode: replace``) and are
        self-contained. Gen 3 cases carry none and get the overlay default.
        """
        state = case.get("environment_state")
        generation = int(case.get("generation") or 3)
        if state is None and generation >= 5:
            raise ValueError(
                f"case {case.get('eval_id', '<unknown>')} declares generation {generation} "
                "but has no environment_state"
            )
        if state is not None and not isinstance(state, dict):
            raise ValueError("environment_state must be a JSON object")
        environment = cls(initial_state=state)
        fault = case.get("fault_injection")
        if fault is not None:
            if not isinstance(fault, dict) or not isinstance(fault.get("tool"), str) or not fault["tool"].strip():
                raise ValueError("fault_injection must identify a nonempty tool name")
            environment.inject_fault(
                tool_name=fault["tool"],
                status_code=fault.get("status_code", 503),
                error=fault.get("error", "Service Unavailable"),
            )
        return environment

    def _load_state(self, state_config: Optional[Dict[str, Any]] = None) -> None:
        """Populates internal dataclasses from default state or provided config."""
        mode = str((state_config or {}).get("mode", "overlay"))
        if mode not in ("overlay", "replace"):
            raise ValueError(f"environment_state mode must be 'overlay' or 'replace', got {mode!r}")
        self.mode = mode
        if mode == "overlay":
            self.hosts = _get_default_hosts()
            self.domains = _get_default_domains()
            self.hashes = _get_default_hashes()
            self.cases = _get_default_cases()
            self.ips = _get_default_ips()
        else:
            self.hosts = {}
            self.domains = {}
            self.hashes = {}
            self.cases = {}
            self.ips = {}
        self.events = []
        self.blocked_indicators = set()
        self.action_history = []
        self.faults = {}

        if not state_config:
            return

        if "hosts" in state_config:
            for k, v in state_config["hosts"].items():
                if isinstance(v, HostEntity):
                    self.hosts[k] = deepcopy(v)
                elif isinstance(v, dict):
                    self.hosts[k] = HostEntity(**v)

        if "domains" in state_config:
            for k, v in state_config["domains"].items():
                if isinstance(v, DomainEntity):
                    self.domains[k] = deepcopy(v)
                elif isinstance(v, dict):
                    self.domains[k] = DomainEntity(**v)

        if "hashes" in state_config:
            for k, v in state_config["hashes"].items():
                if isinstance(v, HashEntity):
                    self.hashes[k] = deepcopy(v)
                elif isinstance(v, dict):
                    self.hashes[k] = HashEntity(**v)

        if "cases" in state_config:
            for k, v in state_config["cases"].items():
                if isinstance(v, CaseEntity):
                    self.cases[k] = deepcopy(v)
                elif isinstance(v, dict):
                    self.cases[k] = CaseEntity(**v)

        if "ips" in state_config:
            for k, v in state_config["ips"].items():
                if isinstance(v, IpIndicatorEntity):
                    self.ips[k] = deepcopy(v)
                elif isinstance(v, dict):
                    self.ips[k] = IpIndicatorEntity(**v)

        if "events" in state_config:
            self.events = [deepcopy(e) for e in state_config["events"] if isinstance(e, dict)]

        if "blocked_indicators" in state_config:
            self.blocked_indicators = set(state_config["blocked_indicators"])

        if "faults" in state_config:
            self.faults = deepcopy(state_config["faults"])

    def inject_fault(
        self,
        tool_name: str,
        status_code: int = 503,
        error: str = "Service Unavailable",
    ) -> None:
        """Simulates upstream tool failure or service degradation."""
        self.faults[tool_name] = {
            "status_code": status_code,
            "error": error,
        }

    def clear_faults(self) -> None:
        """Clears all injected faults from the environment."""
        self.faults.clear()

    def reset(self) -> None:
        """Resets the state machine back to its initial configuration."""
        self._load_state(self._initial_state_config)

    def get_state_snapshot(self) -> Dict[str, Any]:
        """Returns a serialized snapshot of the active environment state."""
        return {
            "mode": self.mode,
            "hosts": {k: asdict(v) for k, v in self.hosts.items()},
            "domains": {k: asdict(v) for k, v in self.domains.items()},
            "hashes": {k: asdict(v) for k, v in self.hashes.items()},
            "cases": {k: asdict(v) for k, v in self.cases.items()},
            "ips": {k: asdict(v) for k, v in self.ips.items()},
            "events": deepcopy(self.events),
            "blocked_indicators": sorted(list(self.blocked_indicators)),
            "action_history": [asdict(a) for a in self.action_history],
            "faults": deepcopy(self.faults),
        }

    def _find_host(self, identifier: str) -> Optional[HostEntity]:
        """Finds host entity by hostname or IP address."""
        clean_id = str(identifier).strip()
        if clean_id in self.hosts:
            return self.hosts[clean_id]
        for host in self.hosts.values():
            if host.ip == clean_id or host.hostname.lower() == clean_id.lower():
                return host
        return None

    def _ip_report(self, ip: str) -> Dict[str, Any]:
        """Inventory first, then the mode-specific fallback."""
        if ip in self.ips:
            return self.ips[ip].to_report()
        host = self._find_host(ip)
        if self.strict:
            return self._strict_ip_fallback(ip, host)
        return self._legacy_ip_fallback(ip, host)

    def _strict_ip_fallback(self, ip: str, host: Optional[HostEntity]) -> Dict[str, Any]:
        """Replace-mode fallback: structural facts only, no fabricated reputation."""
        cidr = _slash24(ip)
        if host is not None:
            return {
                "ip": ip,
                "category": "Internal Corporate Subnet",
                "reputation": "INTERNAL",
                "verdict": "NEUTRAL",
                "host_association": host.hostname,
                "criticality_tier": host.criticality_tier,
                "asn": "RFC-1918 (Private Corporate Network)",
                "cidr": cidr,
                "routing_status": "RFC-1918 (Non-Routable Private Subnet)",
                "malicious_votes": 0,
                "harmless_votes": 0,
                "vt_positives": 0,
                "vt_total": 72,
                "reverse_dns": f"{host.hostname.lower()}.corp.internal",
            }
        if ip.startswith(_RFC5737_PREFIXES):
            rfc_num = "1" if ip.startswith("192.0.2.") else ("2" if ip.startswith("198.51.100.") else "3")
            return {
                "ip": ip,
                "category": "Documentation / Reserved RFC-5737",
                "reputation": "BENIGN / NON-ROUTABLE",
                "verdict": "SAFE",
                "malicious_votes": 0,
                "harmless_votes": 0,
                "asn": "AS0 (Documentation)",
                "cidr": cidr,
                "routing_status": f"RFC-5737 TEST-NET-{rfc_num} (Non-Routable Documentation Subnet)",
                "vt_positives": 0,
                "vt_total": 72,
                "reverse_dns": "",
            }
        if _is_rfc1918(ip):
            return {
                "ip": ip,
                "category": "Internal Corporate Subnet",
                "reputation": "INTERNAL",
                "verdict": "NEUTRAL",
                "host_association": "Unknown",
                "asn": "RFC-1918 (Private Corporate Network)",
                "cidr": cidr,
                "routing_status": "RFC-1918 (Non-Routable Private Subnet)",
                "malicious_votes": 0,
                "harmless_votes": 0,
                "vt_positives": 0,
                "vt_total": 72,
                "reverse_dns": "",
            }
        return {
            "ip": ip,
            "category": "Public IP",
            "reputation": "NO_DATA",
            "verdict": "UNKNOWN",
            "malicious_votes": 0,
            "harmless_votes": 0,
            "asn": "Unknown",
            "cidr": cidr,
            "routing_status": "Public Routable IP",
            "vt_positives": 0,
            "vt_total": 72,
            "reverse_dns": "",
        }

    def _legacy_ip_fallback(self, ip: str, host: Optional[HostEntity]) -> Dict[str, Any]:
        """Overlay-mode fallback: the Gen 3 behavior, moved verbatim.

        The two exact-match special cases (10.0.99.50 and 198.51.100.42) are not
        here because they now live in _get_default_ips() and are served by the
        inventory lookup in _ip_report before this method runs.
        """
        if ip.startswith("192.0.2.") or ip.startswith("198.51.100.") or ip.startswith("203.0.113."):
            rfc_num = "1" if ip.startswith("192.0.2.") else ("2" if ip.startswith("198.51.100.") else "3")
            cidr_prefix = "192.0.2.0/24" if ip.startswith("192.0.2.") else ("198.51.100.0/24" if ip.startswith("198.51.100.") else "203.0.113.0/24")
            return {
                "ip": ip,
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
                "reverse_dns": f"test-doc-{ip.replace('.', '-')}.example.net",
            }
        if ip in ["10.0.4.15", "10.0.5.23", "10.0.8.99"] or (host is not None):
            host_name = host.hostname if host else ("DESKTOP-FIN-08" if ip == "10.0.5.23" else "Unknown")
            return {
                "ip": ip,
                "category": "Internal Corporate Subnet",
                "reputation": "INTERNAL",
                "verdict": "NEUTRAL",
                "host_association": host_name,
                "criticality_tier": host.criticality_tier if host else "STANDARD",
                "asn": "RFC-1918 (Private Corporate Network)",
                "cidr": "10.0.0.0/16",
                "routing_status": "RFC-1918 (Non-Routable Private Subnet)",
                "vt_positives": 0,
                "vt_total": 72,
                "reverse_dns": f"{host_name.lower()}.corp.internal",
                "malicious_votes": 0,
                "harmless_votes": 100,
            }
        return {
            "ip": ip,
            "category": "Public IP",
            "reputation": "SUSPICIOUS",
            "verdict": "POTENTIALLY_MALICIOUS",
            "malicious_votes": 42,
            "harmless_votes": 2,
            "asn": "AS13335 (Public Transit)",
            "cidr": f"{ip.rsplit('.', 1)[0]}.0/24",
            "routing_status": "Public Routable IP",
            "vt_positives": 42,
            "vt_total": 72,
            "reverse_dns": f"host-{ip.replace('.', '-')}.isp-routing.net",
        }

    def query_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Executes epistemic information-gathering tool queries against the sandbox state."""
        # 1. Check for active fault injection on this tool
        if tool_name in self.faults:
            fault = self.faults[tool_name]
            return {
                "error": fault["error"],
                "status_code": fault["status_code"],
                "status": "ERROR",
            }

        args = dict(arguments or {})

        # 2. IP address report query
        if tool_name in ["get_ip_address_report", "get_ip_report"]:
            ip = str(args.get("ip") or args.get("entity_id") or args.get("query") or "").strip()
            return self._ip_report(ip)

        # 3. Domain report query
        if tool_name == "get_domain_report":
            domain = str(args.get("domain") or args.get("query") or "").strip().lower()
            if domain == "error-503.service-unavailable.org":
                return {
                    "error": "HTTP 503: Upstream Threat Intelligence Service Unavailable",
                    "status_code": 503,
                    "domain": domain,
                }
            if domain in self.domains:
                ent = self.domains[domain]
                res = {
                    "domain": ent.domain,
                    "verdict": ent.verdict,
                    "category": ent.category,
                    "categories": ent.categories if ent.categories else [ent.category],
                    "reputation": ent.reputation,
                    "malicious_votes": ent.malicious_votes,
                    "harmless_votes": ent.harmless_votes,
                    "vt_positives": ent.vt_positives if ent.vt_positives else ent.malicious_votes,
                    "vt_total": ent.vt_total if ent.vt_total else 72,
                    "registrar": ent.registrar,
                    "created_date": ent.created_date or ent.first_seen or "2026-01-01",
                    "threat_family": ent.threat_family,
                    "passive_dns": ent.passive_dns if ent.passive_dns else ent.resolutions,
                    "resolutions": ent.resolutions if ent.resolutions else ent.passive_dns,
                }
                if ent.first_seen:
                    res["first_seen"] = ent.first_seen
                return res
            return {
                "domain": domain,
                "verdict": "BENIGN",
                "category": "Uncategorized Domain",
                "categories": ["Uncategorized Domain"],
                "reputation": "BENIGN",
                "threat_family": "None",
                "malicious_votes": 0,
                "harmless_votes": 95,
                "vt_positives": 0,
                "vt_total": 72,
                "registrar": "MarkMonitor Inc.",
                "created_date": "2020-01-01",
                "passive_dns": ["192.0.2.1"],
                "resolutions": ["192.0.2.1"],
            }

        # 4. File report query
        if tool_name == "get_file_report":
            file_hash = str(args.get("file_hash") or args.get("hash") or args.get("sha256") or "").strip()
            if file_hash in self.hashes:
                h = self.hashes[file_hash]
                return {
                    "hash": h.sha256,
                    "hash_type": "SHA-256",
                    "filename": h.filename,
                    "verdict": h.verdict,
                    "threat_name": h.threat_name,
                    "certificate_status": h.certificate_status,
                    "cert_status": h.cert_status,
                    "vendor": h.vendor,
                    "signer": h.signer,
                    "revocation_date": h.revocation_date,
                    "vt_positives": h.vt_positives,
                    "vt_total": h.vt_total,
                    "detections": h.detections,
                }
            return {
                "hash": file_hash,
                "hash_type": "MD5" if len(file_hash) == 32 else "SHA-256",
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
            }

        # 5. Entity lookup / summarization
        if tool_name in ["lookup_entity", "summarize_entity"]:
            entity_id = str(args.get("entity_id") or args.get("query") or args.get("entity") or "").strip()
            entity_type = str(args.get("entity_type") or args.get("type") or "host").strip()
            host = self._find_host(entity_id)
            if host:
                is_hr = host.hostname == "DESKTOP-HR-04" or host.ip == "10.0.8.99"
                if is_hr:
                    return {
                        "entity": host.hostname,
                        "entity_type": entity_type,
                        "ip": host.ip,
                        "criticality_tier": host.criticality_tier,
                        "isolated": host.isolated,
                        "active_user": host.active_user,
                        "os": host.os,
                        "installed_services": host.installed_services,
                        "siem_events_found": 28,
                        "recent_event_types": ["VPN_AUTHENTICATION", "PROCESS_LAUNCH", "SMB_SESSION"],
                        "process_command": "psexec.exe -u admin -p ... \\\\10.0.8.99 cmd.exe",
                        "target_host": "10.0.8.99",
                        "suspicious_indicators": True,
                        "last_active": "2026-08-31T18:00:00Z",
                        "source_ip": "10.0.8.99",
                        "logon_type": "Type 3 Network Logon",
                        "process_tree": [
                            {
                                "pid": 1044,
                                "ppid": 420,
                                "process_name": "explorer.exe",
                                "command_line": "C:\\Windows\\explorer.exe",
                                "user": host.active_user,
                            },
                            {
                                "pid": 4820,
                                "ppid": 1044,
                                "process_name": "cmd.exe",
                                "command_line": "cmd.exe /c psexec.exe -u admin -p ... \\\\10.0.8.99 cmd.exe",
                                "user": host.active_user,
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
                                "user": host.active_user,
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
                    }
                else:
                    return {
                        "entity": host.hostname,
                        "entity_type": entity_type,
                        "ip": host.ip,
                        "criticality_tier": host.criticality_tier,
                        "isolated": host.isolated,
                        "active_user": host.active_user,
                        "os": host.os,
                        "installed_services": host.installed_services,
                        "siem_events_found": 14,
                        "recent_event_types": ["USER_LOGIN", "NETWORK_CONNECTION", "PROCESS_LAUNCH"],
                        "suspicious_indicators": True if "FIN" in host.hostname else False,
                        "last_active": "2026-08-31T18:00:00Z",
                        "source_ip": host.ip,
                        "logon_type": "Type 2 Interactive Logon",
                        "process_tree": [
                            {
                                "pid": 1100,
                                "ppid": 450,
                                "process_name": "explorer.exe",
                                "command_line": "C:\\Windows\\explorer.exe",
                                "user": host.active_user,
                            },
                            {
                                "pid": 2480,
                                "ppid": 1100,
                                "process_name": "powershell.exe" if "FIN" in host.hostname else "app.exe",
                                "command_line": "powershell.exe -enc ..." if "FIN" in host.hostname else "app.exe",
                                "user": host.active_user,
                            },
                        ],
                        "events": [
                            {
                                "timestamp": "2026-08-31T17:40:00Z",
                                "event_type": "USER_LOGIN",
                                "user": host.active_user,
                                "logon_type": "Type 2 Interactive Logon",
                                "source_ip": host.ip,
                            },
                            {
                                "timestamp": "2026-08-31T17:45:00Z",
                                "event_type": "NETWORK_CONNECTION",
                                "source_ip": host.ip,
                                "destination_ip": "198.51.100.42",
                                "destination_port": 443,
                            },
                        ],
                    }
            return {
                "entity": entity_id,
                "entity_type": entity_type,
                "siem_events_found": 14,
                "recent_event_types": ["USER_LOGIN", "NETWORK_CONNECTION", "PROCESS_LAUNCH"],
                "suspicious_indicators": True if ("evil" in entity_id or "FIN" in entity_id) else False,
                "last_active": "2026-08-25T14:30:00Z",
                "source_ip": "10.0.5.23" if "FIN" in entity_id else "192.0.2.10",
                "logon_type": "Type 3 Network Logon" if ("HR" in entity_id or "admin" in entity_id) else "Type 2 Interactive Logon",
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
                        "source_ip": "10.0.5.23" if "FIN" in entity_id else "192.0.2.10",
                    }
                ],
            }

        # 6. List SOAR cases
        if tool_name == "list_cases":
            query = str(args.get("query") or args.get("filter_expr") or args.get("filter") or "").lower()
            matching_cases = []
            for case in self.cases.values():
                if (
                    not query
                    or query in case.case_id.lower()
                    or query in case.title.lower()
                    or query in case.priority.lower()
                    or any(query in c.lower() for c in case.comments)
                ):
                    matching_cases.append({
                        "case_id": case.case_id,
                        "title": case.title,
                        "priority": case.priority,
                        "stage": case.stage,
                        "status": case.status,
                        "assigned_to": case.assignee,
                    })
            return {"cases": matching_cases, "total": len(matching_cases)}

        # 7. Get specific SOAR case or alert
        if tool_name in ["get_case", "fetch_alert_data"]:
            case_id = str(args.get("case_id") or args.get("caseId") or args.get("siem_alert_id") or "").strip()
            clean_id = case_id.split("/")[-1]
            if clean_id in self.cases:
                c = self.cases[clean_id]
                return {
                    "case_id": c.case_id,
                    "title": c.title,
                    "priority": c.priority,
                    "stage": c.stage,
                    "status": c.status,
                    "assignee": c.assignee,
                    "comments": c.comments,
                }
            return {
                "error": f"Case or alert '{clean_id}' not found",
                "status": "NOT_FOUND",
            }

        # 8. UDM search
        if tool_name == "udm_search":
            query = str(args.get("query") or "")
            return {
                "query": query,
                "total_events": 5,
                "events": [
                    {
                        "event_timestamp": "2026-08-31T17:45:00Z",
                        "metadata": {"event_type": "NETWORK_CONNECTION"},
                        "principal": {"hostname": "DESKTOP-FIN-08", "ip": "10.0.5.23"},
                        "target": {"hostname": "update-service-win32.com", "ip": "198.51.100.42"},
                    },
                    {
                        "event_timestamp": "2026-08-31T17:46:12Z",
                        "metadata": {"event_type": "PROCESS_LAUNCH"},
                        "principal": {"hostname": "DESKTOP-FIN-08", "user": {"userid": "jdoe"}},
                        "target": {"process": {"command_line": "powershell.exe -enc ..."}},
                    },
                ],
            }

        return {
            "error": f"Tool '{tool_name}' not supported by SocEnvironment",
            "status": "ERROR",
        }

    def execute_action(self, action_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a pragmatic state-changing action in the environment and records it in history."""
        args = dict(arguments or {})
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        result: Dict[str, Any] = {}

        # 1. Isolate host
        if action_name in ["isolate_host", "isolate"]:
            target = str(
                args.get("hostname")
                or args.get("host")
                or args.get("ip")
                or args.get("entity")
                or args.get("target")
                or ""
            ).strip()
            host = self._find_host(target)
            if host:
                host.isolated = True
                result = {
                    "status": "SUCCESS",
                    "action": "isolate_host",
                    "hostname": host.hostname,
                    "ip": host.ip,
                    "criticality_tier": host.criticality_tier,
                    "isolated": True,
                    "message": f"Host '{host.hostname}' ({host.ip}) successfully isolated from network.",
                }
            else:
                result = {
                    "status": "ERROR",
                    "action": "isolate_host",
                    "error": f"Host '{target}' not found in inventory.",
                }

        # 2. Unblock / Unisolate host
        elif action_name in ["unblock_host", "unisolate_host", "unisolate"]:
            target = str(
                args.get("hostname")
                or args.get("host")
                or args.get("ip")
                or args.get("entity")
                or ""
            ).strip()
            host = self._find_host(target)
            if host:
                host.isolated = False
                result = {
                    "status": "SUCCESS",
                    "action": "unblock_host",
                    "hostname": host.hostname,
                    "ip": host.ip,
                    "isolated": False,
                    "message": f"Host '{host.hostname}' network isolation removed.",
                }
            else:
                result = {
                    "status": "ERROR",
                    "action": "unblock_host",
                    "error": f"Host '{target}' not found in inventory.",
                }

        # 3. Block indicator (domain, IP, hash)
        elif action_name in ["block_indicator", "block_domain", "block_ip", "block_hash"]:
            indicator = str(
                args.get("indicator")
                or args.get("domain")
                or args.get("ip")
                or args.get("hash")
                or args.get("value")
                or ""
            ).strip()
            if indicator:
                self.blocked_indicators.add(indicator)
                result = {
                    "status": "SUCCESS",
                    "action": "block_indicator",
                    "indicator": indicator,
                    "message": f"Indicator '{indicator}' added to firewall and EDR blocklist.",
                }
            else:
                result = {
                    "status": "ERROR",
                    "action": "block_indicator",
                    "error": "No valid indicator provided to block.",
                }

        # 4. Update / post case comment
        elif action_name in [
            "update_case_comment",
            "post_case_comment",
            "create_case_comment",
            "add_case_comment",
        ]:
            case_id = str(args.get("case_id") or args.get("caseId") or "").strip().split("/")[-1]
            comment = str(args.get("comment") or args.get("text") or args.get("note") or "").strip()
            if case_id in self.cases:
                c = self.cases[case_id]
                c.comments.append(comment)
                result = {
                    "status": "SUCCESS",
                    "action": "update_case_comment",
                    "case_id": c.case_id,
                    "bytes_posted": len(comment),
                    "total_comments": len(c.comments),
                }
            else:
                result = {
                    "status": "ERROR",
                    "action": "update_case_comment",
                    "error": f"Case '{case_id}' not found.",
                }

        # 5. Close case
        elif action_name in ["close_case", "resolve_case"]:
            case_id = str(args.get("case_id") or args.get("caseId") or "").strip().split("/")[-1]
            verdict = str(args.get("verdict") or args.get("resolution") or "RESOLVED")
            if case_id in self.cases:
                c = self.cases[case_id]
                c.status = "CLOSED"
                c.stage = "RESOLVED"
                result = {
                    "status": "SUCCESS",
                    "action": "close_case",
                    "case_id": c.case_id,
                    "verdict": verdict,
                    "status_value": "CLOSED",
                    "stage": "RESOLVED",
                }
            else:
                result = {
                    "status": "ERROR",
                    "action": "close_case",
                    "error": f"Case '{case_id}' not found.",
                }

        # 6. Unsupported action
        else:
            result = {
                "status": "ERROR",
                "action": action_name,
                "error": f"Unsupported action '{action_name}'",
            }

        # Record action in history
        self.action_history.append(
            EnvironmentAction(
                action_name=action_name,
                arguments=args,
                timestamp=now_ts,
                status=result.get("status", "UNKNOWN"),
                result=result,
            )
        )

        return result
