"""Interactive Threat Hunting Sandbox Environment for GTI Collection & Campaign Sweeps.

Subclasses SocEnvironment (without modifying locked harness files) to provide
deterministic Google Threat Intelligence (GTI) collection/pivot tools and
multi-horizon (72h vs. 168h) Chronicle SIEM telemetry grounded in the
"Unwrapping Ursnif's Gifts" (alienvault_63bbee81b55c8ba00724605a / report--22-00022539)
campaign.
"""

from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any, Dict, List, Optional

from agent.soc_environment import (
    CaseEntity,
    DomainEntity,
    HashEntity,
    HostEntity,
    IpIndicatorEntity,
    SocEnvironment,
)


# Ground-truth hashes from "Unwrapping Ursnif's Gifts" & "superstarts.top" GTI reports
URSNIF_COLLECTION_ID = "alienvault_63bbee81b55c8ba00724605a"
URSNIF_REPORT_ID = "report--22-00022539"
URSNIF_PRIMARY_C2_DOMAIN = "superstarts.top"
URSNIF_C2_IP = "193.106.191.163"
URSNIF_PAYLOAD_SHA256 = "dfdfd0a339fe03549b2475811b106866d035954e9bc002f20b0f69e0f986838f"
URSNIF_DLL_SHA256 = "8e570e32acb99abfd0daf62cff13a09eb694ebfa633a365d224aefc6449f97de"
LOLBIN_RUNDLL32_SHA256 = "7d99c80a1249a1ec9af0f3047c855778b06ea57e11943a271071985afe09e6c2"
BENIGN_NGINX_HTML_SHA256 = "38ffd143fb97ef7ce2fbbe39cbbe8ed1ebdc41eb53b2c68f20cb2be6381eb38e"
PATIENT_ZERO_HOST = "malwaretest-win"
UNALERTED_SOAR_CASE_ID = "CASE-2396"


def get_collection_report(collection_id: str) -> str:
  """Retrieves Google Threat Intelligence (GTI) collection or report metadata, summary, and targeted TTPs.

  Args:
      collection_id: GTI collection or report identifier (e.g. 'alienvault_63bbee81b55c8ba00724605a').
  """
  return json.dumps({"collection_id": collection_id, "status": "SUCCESS"})


def get_entities_related_to_a_collection(
    collection_id: str,
    relationship_name: str = "all",
) -> str:
  """Retrieves IOC entities (domains, files, ip_addresses, attack_techniques) associated with a GTI collection.

  Args:
      collection_id: GTI collection or report identifier.
      relationship_name: Relationship category ('domains', 'files', 'ip_addresses', 'attack_techniques', or 'all').
  """
  return json.dumps({
      "collection_id": collection_id,
      "relationship_name": relationship_name,
  })


def get_entities_related_to_a_domain(
    domain: str,
    relationship_name: str = "communicating_files",
) -> str:
  """Retrieves second-hop entities (such as communicating_files or downloaded_files) related to a domain in GTI.

  Args:
      domain: Domain FQDN string (e.g. 'superstarts.top').
      relationship_name: GTI relationship name (default 'communicating_files').
  """
  return json.dumps({"domain": domain, "relationship_name": relationship_name})


def get_ioc_matches(hours_back: int = 72) -> str:
  """Queries Chronicle SIEM for automated IOC matches across enterprise telemetry within the lookback horizon.

  Args:
      hours_back: Lookback window in hours (default 72; widen to 168 for 7-day historical sweeps).
  """
  return json.dumps({"hours_back": hours_back, "ioc_matches": []})


def search_security_events(query: str, hours_back: int = 72) -> str:
  """Searches Chronicle SIEM UDM security events (DNS, network, process launch, module load) over a lookback window.

  Args:
      query: Search query containing domain, IP, SHA-256 hash, hostname, or UDM event filter.
      hours_back: Lookback window in hours (default 72; widen to 168 when 72h returns zero events).
  """
  return json.dumps({"query": query, "hours_back": hours_back, "events": []})


class ThreatHuntEnvironment(SocEnvironment):
  """Extended SOC Sandbox supporting proactive GTI collection & multi-horizon SIEM threat hunting."""

  supports_threat_hunt_tools: bool = True

  def __init__(self, initial_state: Optional[Dict[str, Any]] = None) -> None:
    self.collections: Dict[str, Dict[str, Any]] = {}
    self.domain_relationships: Dict[str, Dict[str, Any]] = {}
    self.require_horizon_widening: bool = True
    self.min_widened_hours: int = 168
    super().__init__(initial_state=initial_state)

  def _load_state(self, state_config: Optional[Dict[str, Any]] = None) -> None:
    super()._load_state(state_config)
    cfg = state_config or {}
    self.collections = deepcopy(cfg.get("collections", _default_collections()))
    self.domain_relationships = deepcopy(
        cfg.get("domain_relationships", _default_domain_relationships())
    )
    self.require_horizon_widening = bool(
        cfg.get("require_horizon_widening", True)
    )
    self.min_widened_hours = int(cfg.get("min_widened_hours", 168))

  def query_tool(
      self, tool_name: str, arguments: Dict[str, Any]
  ) -> Dict[str, Any]:
    """Executes GTI collection, pivot, and multi-horizon SIEM tools before delegating to SocEnvironment."""
    if tool_name in self.faults:
      fault = self.faults[tool_name]
      return {
          "error": fault["error"],
          "status_code": fault["status_code"],
          "status": "ERROR",
      }

    args = dict(arguments or {})

    if tool_name == "get_collection_report":
      col_id = str(
          args.get("collection_id")
          or args.get("id")
          or args.get("query")
          or args.get("arg")
          or ""
      ).strip()
      if col_id in self.collections:
        col = deepcopy(self.collections[col_id])
        return {
            "status": "SUCCESS",
            "collection_id": col_id,
            "name": col.get("name", col_id),
            "collection_type": col.get("collection_type", "collection"),
            "threat_family": col.get("threat_family", "Ursnif / Gozi (IAP 2.0)"),
            "summary": col.get("summary", ""),
            "attack_techniques": col.get("attack_techniques", []),
            "indicator_counts": {
                "domains": len(col.get("domains", [])),
                "files": len(col.get("files", [])),
                "ip_addresses": len(col.get("ip_addresses", [])),
            },
        }
      return {
          "status": "NOT_FOUND",
          "collection_id": col_id,
          "error": f"Collection '{col_id}' not found in GTI.",
      }

    if tool_name == "get_entities_related_to_a_collection":
      col_id = str(
          args.get("collection_id")
          or args.get("id")
          or args.get("query")
          or args.get("arg")
          or ""
      ).strip()
      rel_name = str(
          args.get("relationship_name")
          or args.get("entity_type")
          or args.get("relationship")
          or "all"
      ).strip().lower()
      if col_id not in self.collections:
        return {
            "status": "NOT_FOUND",
            "collection_id": col_id,
            "error": f"Collection '{col_id}' not found in GTI.",
        }
      col = self.collections[col_id]
      core_keys = ("domains", "files", "ip_addresses", "attack_techniques")
      if rel_name in core_keys:
        return {
            "status": "SUCCESS",
            "collection_id": col_id,
            "relationship_name": rel_name,
            "entities": deepcopy(col.get(rel_name, [])),
            "related_indicators_summary": {
                k: deepcopy(col.get(k, [])) for k in core_keys
            },
        }
      if rel_name in ("all", "", "indicators", "iocs"):
        return {
            "status": "SUCCESS",
            "collection_id": col_id,
            "relationship_name": "all",
            "domains": deepcopy(col.get("domains", [])),
            "files": deepcopy(col.get("files", [])),
            "ip_addresses": deepcopy(col.get("ip_addresses", [])),
            "attack_techniques": deepcopy(col.get("attack_techniques", [])),
        }
      extra_rels = col.get("extra_relationships", {})
      return {
          "status": "SUCCESS",
          "collection_id": col_id,
          "relationship_name": rel_name,
          "entities": deepcopy(extra_rels.get(rel_name, [])),
          "note": (
              "Non-IOC relationship queried. Query 'domains', 'files', or 'all'"
              " to retrieve actionable indicators for SIEM correlation."
          ),
      }

    if tool_name == "get_entities_related_to_a_domain":
      dom = str(
          args.get("domain")
          or args.get("id")
          or args.get("query")
          or args.get("arg")
          or ""
      ).strip().lower()
      rel_name = str(
          args.get("relationship_name")
          or args.get("relationship")
          or "communicating_files"
      ).strip().lower()
      dom_rels = self.domain_relationships.get(dom, {})
      files = deepcopy(dom_rels.get(rel_name, dom_rels.get("communicating_files", [])))
      return {
          "status": "SUCCESS",
          "domain": dom,
          "relationship_name": rel_name,
          "communicating_files": files,
          "total": len(files),
      }

    if tool_name == "get_ioc_matches":
      hours_back = _extract_hours_back(args, default_hours=72)
      if self.require_horizon_widening and hours_back < self.min_widened_hours:
        return {
            "status": "SUCCESS",
            "hours_back": hours_back,
            "total_matches": 0,
            "ioc_matches": [],
            "hint": (
                f"Zero automated IOC matches in the last {hours_back} hours. "
                f"Widen hours_back to {self.min_widened_hours} (7 days) and run "
                "search_security_events across DNS, network, and PROCESS_MODULE_LOAD."
            ),
        }
      matched_events = [
          deepcopy(e)
          for e in self.events
          if e.get("ioc_match", True)
      ]
      return {
          "status": "SUCCESS",
          "hours_back": hours_back,
          "total_matches": len(matched_events),
          "ioc_matches": matched_events,
      }

    if tool_name in ("search_security_events", "udm_search"):
      query = str(
          args.get("query")
          or args.get("text")
          or args.get("filter")
          or args.get("arg")
          or ""
      ).strip()
      hours_back = _extract_hours_back(args, query=query, default_hours=72)
      if self.require_horizon_widening and hours_back < self.min_widened_hours:
        return {
            "status": "SUCCESS",
            "query": query,
            "hours_back": hours_back,
            "total_events": 0,
            "events": [],
            "hint": (
                f"0 events returned over hours_back={hours_back}. "
                f"Historical campaign telemetry may precede 72h; widen hours_back to {self.min_widened_hours} (7 days)."
            ),
        }
      res = self._hunt_udm_search(query)
      res["hours_back"] = hours_back
      res["status"] = "SUCCESS"
      return res

    # Normalize common argument aliases from raw .clinerules / GTI MCP conventions
    if tool_name == "lookup_entity" and "entity_id" not in args:
      for alias in ("entity_value", "entity", "hostname", "host", "indicator", "value", "arg"):
        if alias in args:
          args["entity_id"] = args[alias]
          break
    elif tool_name in ("get_ip_address_report", "get_ip_report") and "ip" not in args:
      for alias in ("ip_address", "address", "indicator", "value", "arg"):
        if alias in args:
          args["ip"] = args[alias]
          break
    elif tool_name == "get_file_report" and "hash" not in args:
      for alias in ("file_hash", "sha256", "md5", "indicator", "value", "arg"):
        if alias in args:
          args["hash"] = args[alias]
          break
    elif tool_name == "get_domain_report" and "domain" not in args:
      for alias in ("domain_name", "fqdn", "indicator", "value", "arg"):
        if alias in args:
          args["domain"] = args[alias]
          break

    return super().query_tool(tool_name, args)

  def _hunt_udm_search(self, query: str) -> Dict[str, Any]:
    """Executes UDM search prioritizing indicator/entity tokens over UDM schema keywords."""
    udm_stopwords = {
        "and", "or", "not", "metadata", "event_type", "principal", "target",
        "src", "dst", "network", "dns", "questions", "name", "process",
        "file", "sha256", "md5", "hostname", "ip", "command_line", "user",
        "userid", "network_dns", "network_connection", "process_launch",
        "process_module_load", "file_creation", "registry_modification",
        "nocase", "true", "false", "hash", "domain", "url", "fqdn", "host",
        "asset", "event", "type", "hours_back", "query", "question",
    }
    raw_tokens = [
        t for t in re.split(r"[^A-Za-z0-9_.-]+", query.lower()) if len(t) >= 3
    ]
    entity_tokens = [
        t for t in raw_tokens
        if t not in udm_stopwords
        and not t.startswith((
            "metadata.", "principal.", "target.", "network.", "dns.", "security_result."
        ))
    ]
    matched: List[Dict[str, Any]] = []
    if entity_tokens:
      for event in self.events:
        blob = json.dumps(event, sort_keys=True, default=str).lower()
        if any(tok in blob for tok in entity_tokens):
          matched.append(deepcopy(event))
        if len(matched) == 50:
          break
    else:
      for event in self.events:
        blob = json.dumps(event, sort_keys=True, default=str).lower()
        if not raw_tokens or any(tok in blob for tok in raw_tokens):
          matched.append(deepcopy(event))
        if len(matched) == 50:
          break
      if not matched and self.events:
        matched = [deepcopy(e) for e in self.events[:50]]
    return {"query": query, "total_events": len(matched), "events": matched}


def _extract_hours_back(
    args: Dict[str, Any],
    query: str = "",
    default_hours: int = 72,
) -> int:
  """Extracts hours_back integer from tool args or query string."""
  raw = (
      args.get("hours_back")
      or args.get("time_frame_hours")
      or args.get("hours")
  )
  if raw is not None:
    try:
      return int(str(raw).strip().rstrip("hH"))
    except ValueError:
      pass
  q_lower = f"{query} {json.dumps(args)}".lower()
  if "168" in q_lower or "7d" in q_lower or "7 days" in q_lower or "336" in q_lower:
    return 168
  if "24" in q_lower and "72" not in q_lower:
    return 24
  return default_hours


def _default_collections() -> Dict[str, Dict[str, Any]]:
  return {
      URSNIF_COLLECTION_ID: {
          "name": "Unwrapping Ursnifs Gifts",
          "collection_type": "collection",
          "threat_family": "Ursnif / Gozi (IAP 2.0)",
          "summary": (
              "Ursnif (Gozi) banking trojan and initial access campaign using "
              "JScript droppers (wscript.exe) with reversed command-line arguments "
              "('hello cexe lldnur revreSretsigeRllD') to invoke signed Windows "
              "rundll32.exe LOLBins that load malicious Ursnif DLL payloads (itsIt.db) "
              "and beacon to .top/.com/.in C2 domains."
          ),
          "domains": [
              "superstarts.top",
              "superliner.top",
              "internetlined.com",
              "superlinez.top",
              "denterdrigx.com",
              "internetlines.in",
          ],
          "files": [
              {
                  "sha256": URSNIF_PAYLOAD_SHA256,
                  "filename": "ursnif_stage1_loader.bin",
                  "note": "Primary campaign file indicator; verify with get_file_report.",
              },
              {
                  "sha256": LOLBIN_RUNDLL32_SHA256,
                  "filename": "123.com (rundll32.exe)",
                  "note": "Associated execution binary; MUST verify with get_file_report to check if signed OS LOLBin before blocking.",
              },
          ],
          "ip_addresses": [URSNIF_C2_IP],
          "attack_techniques": [
              "T1218.011 - System Binary Proxy Execution: Rundll32",
              "T1059.007 - Command and Scripting Interpreter: JavaScript/JScript (wscript.exe)",
              "T1071.001 - Application Layer Protocol: Web/DNS C2",
          ],
          "extra_relationships": {
              "associations": [{"id": "malware--ursnif", "name": "Ursnif / Gozi"}],
              "malware_families": [{"id": "malware--ursnif", "name": "Ursnif"}],
              "threat_actors": [{"id": "actor--itg08", "name": "ITG08 / FIN7-linked affiliate"}],
              "reports": [
                  {
                      "id": "report--252e33f9227d94e22ed03f78164d44ffb9af07b8ca3288d7cd057b53e1859404",
                      "name": "Unwrapping Ursnifs Gifts",
                  },
                  {
                      "id": URSNIF_REPORT_ID,
                      "name": "Ursnif Evolves Alongside Delivery Mechanisms for IAP 2.0",
                  },
              ],
          },
      }
  }


def _default_domain_relationships() -> Dict[str, Dict[str, Any]]:
  return {
      URSNIF_PRIMARY_C2_DOMAIN: {
          "communicating_files": [
              {
                  "sha256": URSNIF_DLL_SHA256,
                  "filename": "itsIt.db",
                  "file_type": "PE32 DLL (Ursnif Module)",
                  "vt_positives": 51,
                  "vt_total": 72,
                  "note": "Second-hop DLL payload communicating with superstarts.top; verify with get_file_report and search PROCESS_MODULE_LOAD.",
              },
              {
                  "sha256": BENIGN_NGINX_HTML_SHA256,
                  "filename": "index.html",
                  "file_type": "HTML document (Default Nginx welcome page)",
                  "vt_positives": 0,
                  "vt_total": 72,
                  "note": "Benign default Nginx web server HTML page; do not block.",
              },
          ]
      }
  }
