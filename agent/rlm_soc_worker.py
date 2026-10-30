"""DSPy RLM (Recursive Language Model) Epistemic Investigation Worker for SOC Tier 1 Triage.

Implements `RLMSOCRunbookWorkerAgent`, an experimental epistemic worker powered by `dspy.RLM`
that explores alert context, CMDB telemetry, threat intelligence, and SIEM/SOAR records inside
a Python REPL environment rather than a truncated text-only ReAct loop.

Key capabilities:
1. Exposes SOC epistemic tools (`lookup_entity`, `get_ip_address_report`, `get_domain_report`,
   `get_file_report`, `list_cases`, and Track 2 threat-hunt tools) inside the RLM Python REPL
   as native dict-returning functions without the 600/1500-char observation truncation of ReAct.
2. Bridges every REPL tool invocation into the canonical `gemma_deploy` tool trajectory format
   with automatic `(tool, args)` call deduplication so `eval_trajectory_verifier.py` and
   `calculate_epistemic_efficiency()` operate identically to `SOCRunbookWorkerAgent`.
3. Enforces epistemic grounding at the `SUBMIT()` boundary via `GuardedSOCInterpreter`:
   rejects zero-tool submissions, enforces Rule 6 (inspect tool outputs before `SUBMIT()`),
   requires local telemetry fallback (`lookup_entity` / `list_cases`) when upstream TI returns
   HTTP 503, and enforces internal SIEM/SOAR telemetry checks on `THREAT_HUNT` sweeps.
4. Supports optional `sub_lm` routing (e.g., `gemini-2.5-flash-lite` for `llm_query` /
   `llm_query_batched`) while keeping pragmatic containment actions (`isolate_host`,
   `block_indicator`, `update_case_comment`, `close_case`) strictly under `SOCSupervisorAgent`.
"""

from __future__ import annotations

import functools
import inspect
import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import dspy
from dspy.primitives.code_interpreter import CodeExecutionError, CodeInterpreter, FinalOutput
from dspy.primitives.local_interpreter import LocalInterpreter

try:
    from agent.hierarchical_soc_agent import (
        SOCRunbookWorkerAgent,
        WorkerInvestigationReport,
        _has_investigation_evidence,
        _risk_from_observations,
    )
    from agent.soc_tier1_agent import _normalize_verdict
except ModuleNotFoundError:
    from hierarchical_soc_agent import (
        SOCRunbookWorkerAgent,
        WorkerInvestigationReport,
        _has_investigation_evidence,
        _risk_from_observations,
    )
    from soc_tier1_agent import _normalize_verdict


CANONICAL_VERDICTS = ("BENIGN", "SUSPICIOUS", "MALICIOUS", "INCONCLUSIVE")


def normalize_rlm_risk_level(raw_risk: Any, trajectory: List[Dict[str, Any]]) -> str:
    """Normalizes RLM-submitted risk_level into one of BENIGN, SUSPICIOUS, MALICIOUS, INCONCLUSIVE."""
    text = str(raw_risk or "").strip().upper()
    if text in CANONICAL_VERDICTS:
        return text
    if any(k in text for k in ("MALICIOUS", "CRITICAL", "ACTIVE_THREAT", "COMPROMISED", "RANSOMWARE", "C2")):
        return "MALICIOUS"
    if any(k in text for k in ("BENIGN", "CLEAN", "FALSE_POSITIVE", "SAFE", "AUTHORIZED", "NON-ROUTABLE", "RFC-5737")):
        return "BENIGN"
    if any(k in text for k in ("INCONCLUSIVE", "DEGRADED", "503", "UNAVAILABLE", "UNKNOWN")):
        obs_risk = _risk_from_observations(trajectory)
        has_503 = any("503" in str(s.get("observation", "")) for s in trajectory)
        if has_503 and obs_risk != "MALICIOUS":
            return "INCONCLUSIVE"
        return obs_risk if obs_risk != "UNKNOWN" else "INCONCLUSIVE"
    if any(k in text for k in ("SUSPICIOUS", "BORDERLINE", "ANOMAL", "DUPLICATE", "REVOKED")):
        return "SUSPICIOUS"
    if text in ("HIGH", "MEDIUM", "LOW"):
        obs_risk = _risk_from_observations(trajectory)
        if obs_risk != "UNKNOWN":
            return obs_risk
        return "MALICIOUS" if text == "HIGH" else ("SUSPICIOUS" if text == "MEDIUM" else "BENIGN")
    normalized = _normalize_verdict(text)
    if normalized != "INCONCLUSIVE":
        return normalized
    obs_risk = _risk_from_observations(trajectory)
    return obs_risk if obs_risk != "UNKNOWN" else "INCONCLUSIVE"


def normalize_rlm_entities(
    raw_entities: Any,
    trajectory: List[Dict[str, Any]],
    prompt: str = "",
    classification: str = "",
) -> List[str]:
    """Normalizes RLM target_entities output (which may contain strings or dicts) and merges trajectory entities."""
    entities: List[str] = []
    prompt_lower = (prompt or "").lower()

    def _is_case_allowed(case_str: str) -> bool:
        if classification == "THREAT_HUNT" or not prompt_lower:
            return True
        num = re.sub(r"^CASE-", "", case_str.strip(), flags=re.IGNORECASE)
        return case_str.lower() in prompt_lower or (num and num.lower() in prompt_lower)

    def _add(val: Any) -> None:
        if val is None:
            return
        if isinstance(val, dict):
            for k in ("entity_id", "entity", "id", "value", "hostname", "ip", "domain", "file_hash", "hash", "case_id"):
                if k in val and val[k]:
                    _add(val[k])
            return
        if isinstance(val, (list, tuple, set)):
            for item in val:
                _add(item)
            return
        s = str(val).strip()
        if not s:
            return
        if s.upper().startswith("CASE-") and not _is_case_allowed(s):
            return
        if s not in entities:
            entities.append(s)

    _add(raw_entities)

    for step in trajectory:
        tool = str(step.get("tool") or "")
        if not tool:
            continue
        args = step.get("args") or {}
        for k, v in args.items():
            if k in {"entity_type", "hours_back", "limit", "status", "query"}:
                continue
            _add(v)
        obs = str(step.get("observation") or "")
        obs_cases = list(dict.fromkeys(re.findall(r"\bCASE-[A-Z0-9]+(?:-[A-Z0-9]+)*\b", obs)))
        if len(obs_cases) == 1 and not any(str(e).upper().startswith("CASE-") for e in entities):
            _add(obs_cases[0])
        for chg_m in re.findall(r"\bCHG-\d+\b", obs, flags=re.IGNORECASE):
            _add(chg_m.upper())

    return entities


def resolve_dspy_model_string(managed_model: Optional[str]) -> Tuple[str, str]:
    """Resolves a gemma_deploy model identifier into (dspy_model_str, vertex_location)."""
    model = (managed_model or "gemini-2.5-flash-lite").strip()
    region = os.environ.get("GCP_REGION") or os.environ.get("GOOGLE_CLOUD_LOCATION") or "us-central1"
    low = model.lower()
    if any(tag in low for tag in ("gemini-3.7", "gemini-3.5", "gemini-3.1", "gemini-3-", "gemma-4")):
        region = "global"
    if "/" not in model:
        model = f"vertex_ai/{model}"
    return model, region


def build_vertex_dspy_lm(
    managed_model: Optional[str],
    project_id: Optional[str] = None,
    region: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
) -> dspy.LM:
    """Builds a DSPy LM configured for Vertex AI Gemini without response caching during evals."""
    dspy_model, inferred_region = resolve_dspy_model_string(managed_model)
    target_region = inferred_region if inferred_region == "global" else (region or inferred_region)
    if project_id:
        os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
        os.environ["VERTEXAI_PROJECT"] = project_id
    os.environ["GOOGLE_CLOUD_LOCATION"] = target_region
    os.environ["VERTEXAI_LOCATION"] = target_region

    kwargs: Dict[str, Any] = {
        "temperature": temperature,
        "cache": False,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return dspy.LM(dspy_model, **kwargs)


class SOCRLMInvestigationSignature(dspy.Signature):
    """You are a Tier 1 SOC Epistemic Investigation Worker operating inside a Python REPL.
    Follow the provided SOC runbook stages (Stage A: Asset Identity & SOAR Case Correlation,
    Stage B: Network Routing & Scope Verification, Stage C: Threat Intelligence Reputation,
    Stage D: Behavioral Corroboration & Risk Assessment) to investigate the alert.

    CRITICAL RULES:
    1. All provided investigation tools (`lookup_entity`, `get_ip_address_report`,
       `get_domain_report`, `get_file_report`, `list_cases`, etc.) are pre-loaded global
       Python functions that return parsed Python `dict` objects directly (do NOT call
       `json.loads()` on tool return values).
    2. In your first REPL step, query the specific entities explicitly named in `alert_prompt`:
       - Call `lookup_entity` for the alerted hostname AND any named username/employee
         (e.g., `lookup_entity(entity_id="...", entity_type="user")`).
       - Call `get_domain_report`, `get_ip_address_report`, or `get_file_report` ONLY for
         domains, IPs, or SHA-256 hashes explicitly named in `alert_prompt` (unless
         `classification == "THREAT_HUNT"`).
       - Call `list_cases` when checking for existing/duplicate SOAR cases, correlating
         host/case history, or pivoting during a tool outage.
       - Always `print()` the returned dictionaries.
    3. Do NOT call `SUBMIT()` in the same step as your first tool calls. Inspect the printed
       tool outputs first, then call `SUBMIT()` in a subsequent step.
    4. If a primary enrichment tool returns HTTP 503 (`status_code: 503` or `Service Unavailable`),
       pivot to local telemetry (`lookup_entity` on the alerted host and `list_cases`), and submit
       `risk_level="INCONCLUSIVE"`.
    5. Calibrate `risk_level` strictly to the primary alert indicator's verified telemetry:
       - `"MALICIOUS"`: Confirmed active threat (C2 beacon, ransomware, credential phishing,
         PsExec lateral movement) where the primary indicator or host telemetry is malicious.
       - `"SUSPICIOUS"`: Borderline/ambiguous indicators (`BORDERLINE_SUSPICIOUS`), binaries
         with `REVOKED_CERTIFICATE`, or duplicate SOAR case correlation/merge checks where no
         new host isolation is warranted.
       - `"BENIGN"`: RFC-5737 documentation subnets (`SAFE` / `NON-ROUTABLE`), authorized
         internal vulnerability scanners (`BENIGN_AUTHORIZED` / `Qualys Scanner`), or
         sanctioned change tickets (`CHG-...`).
       - `"INCONCLUSIVE"`: Upstream tool outage (`HTTP 503 Service Unavailable`).
       Never output `"HIGH"`, `"CRITICAL"`, `"MEDIUM"`, or `"LOW"`.
    """

    alert_prompt: str = dspy.InputField(desc="Incident alert and CMDB asset context to investigate")
    classification: str = dspy.InputField(desc="Operational alert classification category")
    runbook_instructions: str = dspy.InputField(desc="Translated SOC runbook workflow steps")
    target_entities: list = dspy.OutputField(
        desc="List of plain entity strings investigated (hostnames, IPs, domains, SHA-256 hashes, usernames, CASE-... IDs)"
    )
    findings_summary: str = dspy.OutputField(
        desc="Detailed technical findings citing exact tool outputs, reputation scores, process trees, change IDs (CHG-...), CASE-... notes, certificate status, or HTTP 503 errors"
    )
    evidence_items: list = dspy.OutputField(
        desc="List of concise factual evidence strings extracted from tool observations"
    )
    risk_level: str = dspy.OutputField(
        desc="Exact preliminary risk assessment string: BENIGN, SUSPICIOUS, MALICIOUS, or INCONCLUSIVE"
    )


class GuardedSOCInterpreter(LocalInterpreter):
    """LocalInterpreter subclass that enforces SOC epistemic grounding rules when SUBMIT() is called."""

    def __init__(
        self,
        recorded_trajectory: List[Dict[str, Any]],
        classification: str = "C2_BEACON",
        require_observe_before_submit: bool = True,
        execution_timeout: float = 30.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(execution_timeout=execution_timeout, **kwargs)
        self._recorded_trajectory = recorded_trajectory
        self._classification = classification
        self._require_observe_before_submit = require_observe_before_submit

    def execute(self, code: str, variables: dict[str, Any] | None = None) -> Any:
        prior_tool_count = len(self._recorded_trajectory)
        result = super().execute(code, variables)
        if not isinstance(result, FinalOutput):
            return result

        # Guard 1: At least one tool must have been invoked
        if len(self._recorded_trajectory) == 0:
            raise CodeExecutionError(
                "Investigation incomplete: no epistemic investigation tool was called. "
                "Call at least one tool (lookup_entity, get_ip_address_report, get_domain_report, "
                "get_file_report, or list_cases) and print() its output before calling SUBMIT()."
            )

        # Guard 2: Must have usable investigation evidence (if a tool returned 503, must pivot to lookup_entity/list_cases)
        if not _has_investigation_evidence(self._recorded_trajectory):
            raise CodeExecutionError(
                "Primary tool call returned an error or HTTP 503 without verified local telemetry. "
                "Pivot to lookup_entity on the alerted hostname or list_cases to collect verified "
                "local context before calling SUBMIT(risk_level='INCONCLUSIVE', ...)."
            )

        # Guard 3: Threat Hunt must check internal SIEM/SOAR telemetry
        if self._classification == "THREAT_HUNT":
            has_internal = any(
                s.get("tool") in {"get_ioc_matches", "search_security_events", "udm_search", "list_cases", "lookup_entity"}
                and s.get("execution_status", "SUCCESS") == "SUCCESS"
                and '"status": "NOT_FOUND"' not in str(s.get("observation", ""))
                for s in self._recorded_trajectory
            )
            has_outage = any("503" in str(s.get("observation", "")) for s in self._recorded_trajectory)
            if not has_internal and not has_outage:
                raise CodeExecutionError(
                    "Threat hunt incomplete: you only queried external GTI metadata and have not yet "
                    "queried internal SIEM/SOAR telemetry (get_ioc_matches, search_security_events, "
                    "lookup_entity, or list_cases). Query internal telemetry before calling SUBMIT()."
                )

        # Guard 4: Rule 6 - Do not call SUBMIT() in the same step as the very first tool call
        if self._require_observe_before_submit and prior_tool_count == 0:
            obs_summaries = [
                f"{s['tool']}({json.dumps(s.get('args', {}), sort_keys=True)}) -> {str(s.get('observation', ''))[:800]}"
                for s in self._recorded_trajectory
            ]
            raise CodeExecutionError(
                "Rule 6: Do not call SUBMIT() in the same step as your initial tool calls before "
                "reviewing their outputs. Your tool calls executed and returned:\n"
                + "\n".join(obs_summaries)
                + "\nNow review these outputs and call SUBMIT() in the next step."
            )

        return result


class RLMSOCRunbookWorkerAgent(SOCRunbookWorkerAgent):
    """Specialized SOC Sub-Agent that executes epistemic investigation via DSPy RLM."""

    def __init__(
        self,
        classification: str,
        runbook_name: str,
        runbook_content: str,
        project_id: Optional[str] = None,
        region: str = "us-central1",
        endpoint_id: Optional[str] = None,
        cloudrun_url: Optional[str] = None,
        managed_model: Optional[str] = None,
        use_live_mcp: bool = False,
        environment: Optional[Any] = None,
        strip_scaffolding: bool = True,
        sub_model: Optional[str] = None,
        rlm_max_iters: int = 6,
        rlm_max_llm_calls: int = 10,
        max_output_chars: int = 10_000,
        max_finding_chars: int = 8_000,
        require_observe_before_submit: bool = True,
        dspy_lm: Optional[dspy.BaseLM] = None,
        dspy_sub_lm: Optional[dspy.BaseLM] = None,
        interpreter_factory: Optional[Callable[[], CodeInterpreter]] = None,
    ) -> None:
        super().__init__(
            classification=classification,
            runbook_name=runbook_name,
            runbook_content=runbook_content,
            project_id=project_id,
            region=region,
            endpoint_id=endpoint_id,
            cloudrun_url=cloudrun_url,
            managed_model=managed_model,
            use_live_mcp=use_live_mcp,
            environment=environment,
            strip_scaffolding=strip_scaffolding,
        )
        self.name = f"soc_rlm_worker_{classification.lower()}"
        self.sub_model = sub_model
        self.rlm_max_iters = rlm_max_iters
        self.rlm_max_llm_calls = rlm_max_llm_calls
        self.max_output_chars = max_output_chars
        self.max_finding_chars = max_finding_chars
        self.require_observe_before_submit = require_observe_before_submit
        self._dspy_lm = dspy_lm
        self._dspy_sub_lm = dspy_sub_lm
        self._custom_interpreter_factory = interpreter_factory
        self.last_rlm_repl_trajectory: List[Dict[str, Any]] = []

    def _normalize_tool_kwargs(self, tool_name: str, args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes positional and alias keyword arguments from REPL tool calls."""
        primary_param_map = {
            "lookup_entity": "entity_id",
            "get_ip_address_report": "ip",
            "get_domain_report": "domain",
            "get_file_report": "file_hash",
            "list_cases": "query",
            "get_collection_report": "collection_id",
            "get_entities_related_to_a_collection": "collection_id",
            "get_entities_related_to_a_domain": "domain",
            "get_ioc_matches": "hours_back",
            "search_security_events": "query",
            "udm_search": "query",
            "summarize_entity": "entity",
            "get_case": "case_id",
            "fetch_alert_data": "alert_id",
        }
        bound: Dict[str, Any] = dict(kwargs or {})
        primary = primary_param_map.get(tool_name)
        if args and primary and primary not in bound:
            bound[primary] = args[0]
            if tool_name == "lookup_entity" and len(args) > 1 and "entity_type" not in bound:
                bound["entity_type"] = args[1]
            elif tool_name == "get_entities_related_to_a_collection" and len(args) > 1 and "relationship" not in bound:
                bound["relationship"] = args[1]
            elif tool_name == "get_entities_related_to_a_domain" and len(args) > 1 and "relationship" not in bound:
                bound["relationship"] = args[1]
            elif tool_name == "search_security_events" and len(args) > 1 and "hours_back" not in bound:
                bound["hours_back"] = args[1]

        if tool_name == "lookup_entity":
            for alias in ("entity", "hostname", "host", "target", "id", "ip", "user"):
                if alias in bound and "entity_id" not in bound:
                    bound["entity_id"] = bound.pop(alias)
                    break
            bound.setdefault("entity_type", "host")
        elif tool_name == "get_file_report":
            for alias in ("hash", "sha256", "md5", "sha1", "indicator"):
                if alias in bound and "file_hash" not in bound:
                    bound["file_hash"] = bound.pop(alias)
                    break
        elif tool_name == "get_ip_address_report":
            for alias in ("ip_address", "address", "indicator", "entity_id"):
                if alias in bound and "ip" not in bound:
                    bound["ip"] = bound.pop(alias)
                    break
        elif tool_name == "get_domain_report":
            for alias in ("fqdn", "hostname", "indicator", "entity_id"):
                if alias in bound and "domain" not in bound:
                    bound["domain"] = bound.pop(alias)
                    break
        elif tool_name == "list_cases":
            for alias in ("entity", "case_id", "status", "search", "indicator", "hostname"):
                if alias in bound and "query" not in bound:
                    bound["query"] = bound.pop(alias)
                    break
            bound.setdefault("query", "")
        return bound

    def _build_rlm_tools(
        self,
        recorded_trajectory: List[Dict[str, Any]],
        prompt: str = "",
    ) -> List[Callable[..., Any]]:
        """Wraps allowed epistemic tools for dspy.RLM with trajectory recording, scope discipline, and deduplication."""
        call_cache: Dict[Tuple[str, str], Any] = {}
        wrapped_tools: List[Callable[..., Any]] = []
        prompt_lower = (prompt or "").lower()

        def _make_wrapper(tool_name: str, orig_func: Callable[..., Any]) -> Callable[..., Any]:
            orig_doc = inspect.getdoc(orig_func) or f"Executes {tool_name}."
            rlm_doc = f"{orig_doc} (Returns a parsed Python dict directly; do NOT call json.loads on the result.)"

            @functools.wraps(orig_func)
            def _wrapped(*args: Any, **kwargs: Any) -> Any:
                clean_args = self._normalize_tool_kwargs(tool_name, args, kwargs)
                cache_key = (tool_name, json.dumps(clean_args, sort_keys=True, default=str))
                if cache_key in call_cache:
                    return call_cache[cache_key]

                # Enforce alert scope discipline for single-alert triage (non-THREAT_HUNT)
                if (
                    self.classification != "THREAT_HUNT"
                    and prompt_lower
                    and tool_name in ("get_ip_address_report", "get_domain_report", "get_file_report")
                ):
                    ind_val = str(
                        clean_args.get("ip")
                        or clean_args.get("domain")
                        or clean_args.get("file_hash")
                        or ""
                    ).strip()
                    if ind_val and ind_val.lower() not in prompt_lower:
                        out_of_scope = {
                            "status": "OUT_OF_SCOPE",
                            "indicator": ind_val,
                            "note": (
                                f"Indicator '{ind_val}' is not referenced in alert_prompt. "
                                "Restrict enrichment to indicators explicitly named in the alert."
                            ),
                        }
                        call_cache[cache_key] = out_of_scope
                        return out_of_scope

                obs_str = self._execute_tool_action(tool_name, clean_args)
                try:
                    parsed_obs = json.loads(obs_str)
                except (TypeError, ValueError):
                    parsed_obs = {"raw_output": obs_str}

                if (
                    self.classification != "THREAT_HUNT"
                    and prompt_lower
                    and tool_name == "lookup_entity"
                    and isinstance(parsed_obs, dict)
                    and isinstance(parsed_obs.get("events"), list)
                ):
                    filtered_events = []
                    for ev in parsed_obs["events"]:
                        if isinstance(ev, dict) and ev.get("destination_ip"):
                            dip = str(ev["destination_ip"]).strip().lower()
                            if dip and dip not in prompt_lower:
                                continue
                        filtered_events.append(ev)
                    parsed_obs["events"] = filtered_events
                    obs_str = json.dumps(parsed_obs)

                step = self._tool_trajectory_step(
                    len(recorded_trajectory) + 1,
                    tool_name,
                    clean_args,
                    obs_str,
                )
                step["agent"] = "worker"
                step["rlm_repl"] = True
                recorded_trajectory.append(step)

                call_cache[cache_key] = parsed_obs
                return parsed_obs

            _wrapped.__name__ = tool_name
            _wrapped.__qualname__ = tool_name
            _wrapped.__doc__ = rlm_doc
            return _wrapped

        for name, func in self.tools_dict.items():
            if self._is_tool_allowed(name):
                wrapped_tools.append(_make_wrapper(name, func))

        return wrapped_tools

    @staticmethod
    def _accumulate_lm_usage(lm: Optional[dspy.BaseLM], start_idx: int) -> Dict[str, int]:
        """Sums token usage recorded in a DSPy LM's history slice starting at start_idx."""
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        if lm is None or not hasattr(lm, "history"):
            return usage
        for entry in lm.history[start_idx:]:
            u = entry.get("usage") or {}
            p_tok = int(u.get("prompt_tokens") or u.get("input_tokens") or 0)
            c_tok = int(u.get("completion_tokens") or u.get("output_tokens") or 0)
            t_tok = int(u.get("total_tokens") or (p_tok + c_tok))
            usage["prompt_tokens"] += p_tok
            usage["completion_tokens"] += c_tok
            usage["total_tokens"] += t_tok
        return usage

    def investigate(
        self,
        prompt: str,
        max_iterations: int = 5,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
    ) -> Tuple[WorkerInvestigationReport, List[Dict[str, Any]], Dict[str, int]]:
        """Executes epistemic investigation inside a DSPy RLM REPL and returns WorkerInvestigationReport."""
        recorded_trajectory: List[Dict[str, Any]] = []
        rlm_tools = self._build_rlm_tools(recorded_trajectory, prompt=prompt)

        effective_max_iters = max(int(max_iterations or self.rlm_max_iters), self.rlm_max_iters)

        main_lm = self._dspy_lm or build_vertex_dspy_lm(
            managed_model=self.managed_model,
            project_id=self.project_id,
            region=self.region,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        sub_lm = self._dspy_sub_lm
        if sub_lm is None and self.sub_model:
            sub_lm = build_vertex_dspy_lm(
                managed_model=self.sub_model,
                project_id=self.project_id,
                region=self.region,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        main_history_start = len(getattr(main_lm, "history", []))
        sub_history_start = len(getattr(sub_lm, "history", [])) if sub_lm is not None else 0

        if self._custom_interpreter_factory is not None:
            factory = self._custom_interpreter_factory
        else:
            def factory() -> CodeInterpreter:
                return GuardedSOCInterpreter(
                    recorded_trajectory=recorded_trajectory,
                    classification=self.classification,
                    require_observe_before_submit=self.require_observe_before_submit,
                )

        rlm_module = dspy.RLM(
            SOCRLMInvestigationSignature,
            max_iters=effective_max_iters,
            max_llm_calls=self.rlm_max_llm_calls,
            max_output_chars=self.max_output_chars,
            tools=rlm_tools,
            sub_lm=sub_lm,
            interpreter_factory=factory,
        )

        with dspy.context(lm=main_lm):
            prediction = rlm_module(
                alert_prompt=prompt,
                classification=self.classification,
                runbook_instructions=self.system_instruction,
            )

        self.last_rlm_repl_trajectory = list(getattr(prediction, "trajectory", []) or [])
        self.last_backend = f"DSPy RLM ({getattr(main_lm, 'model', self.managed_model or 'gemini')})"

        main_usage = self._accumulate_lm_usage(main_lm, main_history_start)
        sub_usage = self._accumulate_lm_usage(sub_lm, sub_history_start) if sub_lm is not None else {
            "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0
        }
        total_usage = {
            "prompt_tokens": main_usage["prompt_tokens"] + sub_usage["prompt_tokens"],
            "completion_tokens": main_usage["completion_tokens"] + sub_usage["completion_tokens"],
            "total_tokens": main_usage["total_tokens"] + sub_usage["total_tokens"],
        }

        if not _has_investigation_evidence(recorded_trajectory):
            return (
                WorkerInvestigationReport(
                    classification=self.classification,
                    runbook_name=self.runbook_name,
                    risk_level="UNKNOWN",
                    recommended_escalation="Tier 2: investigation incomplete",
                    raw_response=str(getattr(prediction, "findings_summary", "") or "Investigation incomplete."),
                ),
                recorded_trajectory,
                total_usage,
            )

        target_entities = normalize_rlm_entities(
            getattr(prediction, "target_entities", None),
            recorded_trajectory,
            prompt=prompt,
            classification=self.classification,
        )
        risk_level = normalize_rlm_risk_level(
            getattr(prediction, "risk_level", None),
            recorded_trajectory,
        )
        findings_summary = str(getattr(prediction, "findings_summary", "") or "").strip()
        raw_evidence_items = getattr(prediction, "evidence_items", None) or []
        if isinstance(raw_evidence_items, str):
            raw_evidence_items = [raw_evidence_items]
        evidence: List[str] = [str(item).strip() for item in raw_evidence_items if str(item).strip()]

        # Populate full (untruncated up to max_finding_chars) tool observations for supervisor synthesis
        findings: Dict[str, Any] = {}
        for step in recorded_trajectory:
            tool = str(step.get("tool") or "")
            if not tool:
                continue
            s_args = step.get("args") or {}
            s_obs = str(step.get("observation") or "")
            call_repr = f"{tool}({json.dumps(s_args, sort_keys=True)})"
            findings[call_repr] = s_obs[: self.max_finding_chars]
            ev_entry = f"{tool}: {s_obs[: self.max_finding_chars]}"
            if ev_entry not in evidence:
                evidence.append(ev_entry)

        if findings_summary:
            findings["rlm_synthesis"] = findings_summary

        worker_report_payload = {
            "classification": self.classification,
            "target_entities": target_entities,
            "findings": findings,
            "evidence": evidence,
            "risk_level": risk_level,
            "rlm_repl_steps": len(self.last_rlm_repl_trajectory),
        }
        formatted_raw_response = (
            "[Context & Enrichment]\n"
            f"- Entities Investigated: {', '.join(target_entities) if target_entities else 'None'}\n"
            f"- RLM REPL Iterations: {len(self.last_rlm_repl_trajectory)}\n\n"
            "[Findings & Evidence]\n"
            f"{findings_summary or 'See structured tool observations.'}\n\n"
            "[Preliminary Risk Assessment]\n"
            f"Verdict: {risk_level}\n\n"
            "```worker_report\n"
            f"{json.dumps(worker_report_payload, indent=2)}\n"
            "```"
        )

        report = WorkerInvestigationReport(
            classification=self.classification,
            runbook_name=self.runbook_name,
            target_entities=target_entities,
            findings=findings,
            evidence=evidence,
            risk_level=risk_level,
            recommended_escalation="Tier 2 Responder" if risk_level == "MALICIOUS" else None,
            raw_response=formatted_raw_response,
        )
        return report, recorded_trajectory, total_usage
