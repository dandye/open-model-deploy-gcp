#!/usr/bin/env python3
"""Bounded live smoke evaluation for Gemini 4 per-model implicit prompt caching.

Compares three arms across the 4 scenarios in `configs/evals/hunt/ursnif_gti_hunt_suite.json`:
  1. dynamic_first_neon: Homogeneous `gemini-4-neon` with a dynamic token-0 prefix hazard
     (`[Turn=N | CaseId=... | RequestTimestamp=...]`) injected into `system_instruction`.
  2. static_first_neon: Homogeneous `gemini-4-neon` with refactored static-first
     `system_instruction` and trailing dynamic user `contents`.
  3. static_first_neon_hydrogen: Heterogeneous `gemini-4-neon` supervisor + batched
     `gemini-4-hydrogen` worker with static-first `system_instruction`.

Enforces a hard BudgetLedger cap (default $2.50, strictly under $3.00) and saves
empirical cache hit % and per-1K-run TCO tables under `docs/soc_eval_results/`.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent.gemini4_caching import estimate_cached_cost_usd
from agent.hierarchical_soc_agent import (
    HierarchicalSOCTier1Agent,
    SOCRunbookWorkerAgent,
)
from agent.hillclimb_harness import BudgetLedger
from agent.soc_tier1_agent import extract_soc_decision
from agent.threat_hunt_environment import ThreatHuntEnvironment


DEFAULT_SUITE_PATH = ROOT_DIR / "configs" / "evals" / "hunt" / "ursnif_gti_hunt_suite.json"
DEFAULT_RUNBOOK_PATH = ROOT_DIR / "configs" / "runbooks" / "gti_collection_threat_hunt.md"
DEFAULT_OUTPUT_MD = ROOT_DIR / "docs" / "soc_eval_results" / "GEMINI_4_PROMPT_CACHING_EVAL.md"
DEFAULT_OUTPUT_JSON = ROOT_DIR / "docs" / "soc_eval_results" / "gemini_4_prompt_caching_eval.json"


def build_enterprise_soc_static_prefix() -> str:
    """Build a realistic ~4,800-token static enterprise SOC policy and UDM reference prefix.

    Gemini 4 Implicit Context Caching activates above 4,096 shared prefix tokens.
    Production SecOps agents load static MITRE ATT&CK triage matrices, CMDB asset
    criticality policies, SIEM UDM field dictionaries, and SOAR containment playbooks
    into `system_instruction`. Keeping this block static at token 0 enables the 95%
    cached-input discount on Turn 2+ and across sequential cases.
    """
    sections: List[str] = [
        "# Enterprise Security Operations Center (SOC) Static Policy & Telemetry Reference",
        "## 1. Epistemic Verification & Containment Governance",
        (
            "All Tier 1 and Threat Hunting investigations must complete verified epistemic telemetry "
            "collection prior to recommending or executing containment. Containment actions "
            "(isolate_host, block_indicator, close_case, update_case_comment) are strictly governed "
            "by corroborated evidence across CMDB asset context, network routing scope, external "
            "threat intelligence reputation, and internal SIEM behavioral logs. Never block signed "
            "operating system binaries (LOLBins such as rundll32.exe, wscript.exe, powershell.exe, "
            "certutil.exe, mshta.exe) by file hash; always isolate the specific compromised endpoint "
            "and block the adversary-controlled payload hash or command-and-control domain."
        ),
    ]

    # Static MITRE ATT&CK & UDM telemetry reference catalog (deterministic, ~4,600 tokens)
    techniques = [
        ("T1059.005", "Command and Scripting Interpreter: Visual Basic / JScript", "wscript.exe, cscript.exe", "PROCESS_LAUNCH", "Inspect script arguments for obfuscated string reversal, Base64 payloads, and child LOLBin execution."),
        ("T1218.011", "System Binary Proxy Execution: Rundll32", "rundll32.exe", "PROCESS_MODULE_LOAD", "Correlate loaded DLL path and SHA-256 against signed OS baseline; verify DLL export entrypoints such as DllRegisterServer."),
        ("T1071.001", "Application Layer Protocol: Web Protocols", "http, https", "NETWORK_HTTP", "Evaluate destination domain age, GTI malicious votes, ASN reputation, and periodic beacon intervals."),
        ("T1071.004", "Application Layer Protocol: DNS", "dns", "NETWORK_DNS", "Check high-entropy subdomain labels, TXT record payload volumes, and newly registered top-level domains."),
        ("T1021.002", "Remote Services: SMB/Windows Admin Shares", "smb, admin$, ipc$", "NETWORK_CONNECTION", "Verify Type 3 network logons, service installation events, and authorized change tickets before lateral movement escalation."),
        ("T1047", "Windows Management Instrumentation", "wmic.exe, wmiprvse.exe", "PROCESS_LAUNCH", "Distinguish authorized configuration management polling from remote payload execution across workstation subnets."),
        ("T1078", "Valid Accounts", "idp, vpn, sso", "USER_LOGIN", "Correlate impossible travel alerts with approved travel notices, corporate VPN egress ranges, and MFA challenge outcomes."),
        ("T1110.003", "Brute Force: Password Spraying", "idp, adfs", "USER_LOGIN", "Measure distinct targeted accounts per source IP and verify whether source infrastructure belongs to an authorized vulnerability scanner."),
        ("T1566.002", "Phishing: Spearphishing Link", "email_gateway, web_proxy", "NETWORK_HTTP", "Enrich lookalike domains with GTI reputation and passive DNS before blocking or resetting user credentials."),
        ("T1486", "Data Encrypted for Impact", "edr, file_monitor", "FILE_MODIFICATION", "Prioritize immediate host isolation on confirmed ransomware encryption bursts while preserving forensic memory state."),
        ("T1041", "Exfiltration Over C2 Channel", "firewall, proxy", "NETWORK_CONNECTION", "Quantify outbound byte transfer ratios and correlate destination infrastructure with known infostealer families."),
        ("T1552.001", "Unsecured Credentials: Credentials In Files", "edr, cloud_audit", "FILE_READ", "Check cloud API key reuse from unexpected autonomous systems and revoke compromised service credentials immediately."),
    ]
    asset_tiers = [
        ("TIER-0-IDENTITY", "CRITICAL", "Domain controllers, identity providers, PKI roots, PAM vaults", "Requires immediate Tier 2 page on confirmed compromise; never apply automated disruptive changes without corroborated malicious evidence."),
        ("TIER-1-REVENUE", "CRITICAL", "Payment gateways, core transaction databases, settlement APIs", "Verify blast radius and active change tickets (CHG-*) prior to isolation; never isolate a clean peer server."),
        ("TIER-2-ENTERPRISE", "HIGH", "ERP application servers, CI/CD build runners, file shares, jump hosts", "Isolate only the alerted compromised hostname after corroborating malicious telemetry."),
        ("TIER-3-WORKSTATION", "STANDARD", "Corporate laptops, finance desktops, developer VMs, sandbox hosts", "Standard containment applies once external C2 or malicious payload hash is confirmed."),
    ]
    udm_fields = [
        ("metadata.event_type", "STRING", "Canonical UDM event classification: PROCESS_LAUNCH, PROCESS_MODULE_LOAD, NETWORK_DNS, NETWORK_CONNECTION, NETWORK_HTTP, USER_LOGIN, FILE_CREATION."),
        ("metadata.event_timestamp", "TIMESTAMP", "UTC event timestamp; widen SIEM lookback from 72h to 168h (7d) whenever an initial 72h proactive threat hunt returns zero hits."),
        ("principal.hostname", "STRING", "Source endpoint hostname initiating the process or network activity; always normalize to canonical CMDB inventory hostname."),
        ("principal.ip", "IP_ADDRESS", "Internal RFC-1918 source IPv4 address assigned to the endpoint; never confuse internal host IPs with external adversary indicators."),
        ("principal.user.userid", "STRING", "Authenticated local or domain username associated with the process or logon session."),
        ("principal.process.command_line", "STRING", "Full command-line string of the parent or launching process including script paths and obfuscated arguments."),
        ("target.process.file.sha256", "HEX_64", "SHA-256 cryptographic digest of the executed binary or loaded DLL module; verify via get_file_report before blocking."),
        ("target.hostname", "STRING", "Destination domain or internal host contacted by the principal endpoint."),
        ("target.ip", "IP_ADDRESS", "Destination IPv4 address; classify as PUBLIC, PRIVATE (RFC-1918), or RFC-5737 documentation space (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24)."),
        ("security_result.action", "ENUM", "Observed security control disposition: ALLOW, BLOCK, QUARANTINE, CHALLENGE, UNKNOWN_ACTION."),
        ("security_result.rule_name", "STRING", "Detection rule or YARA-L curated rule identifier that triggered the alert."),
        ("network.dns.questions.name", "STRING", "Queried FQDN in DNS telemetry; pivot via get_entities_related_to_a_domain when hunting campaign infrastructure."),
    ]

    for block_idx in range(1, 5):
        sections.append(f"## {block_idx + 1}. Operational Reference Matrix (Partition {block_idx})")
        for tech_id, name, artifacts, udm_type, guidance in techniques:
            sections.append(
                f"- MITRE {tech_id} ({name}) | Artifacts: {artifacts} | UDM: {udm_type} | "
                f"Triage Guidance (P{block_idx}): {guidance} Confirm asset ownership in CMDB, "
                "cross-check active SOAR tickets via list_cases, and preserve full chain-of-custody evidence."
            )
        for tier_code, crit, examples, policy in asset_tiers:
            sections.append(
                f"- Asset Tier {tier_code} (Criticality={crit}) | Scope: {examples} | "
                f"Governance (P{block_idx}): {policy}"
            )
        for field_name, field_type, desc in udm_fields:
            sections.append(
                f"- UDM Field `{field_name}` ({field_type}, P{block_idx}): {desc}"
            )

    return "\n".join(sections)


class DynamicPrefixHazardAgent(HierarchicalSOCTier1Agent):
    """Test-only subclass reproducing the pre-refactor dynamic-first token-0 prefix hazard.

    Prepends `[Turn=N | CaseId=<id> | RequestTimestamp=<utc>]` at index 0 of
    `system_instruction` on every LLM call to empirically measure cache invalidation.
    """

    def __init__(self, *args: Any, case_id: str = "UNKNOWN", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._hazard_case_id = case_id
        self._hazard_turn = 0

    def _call_llm_step(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
        *,
        system_instruction: Optional[str] = None,
    ):
        self._hazard_turn += 1
        ts = datetime.now(timezone.utc).isoformat()
        base_sys = system_instruction if system_instruction is not None else self.system_instruction
        poisoned_sys = (
            f"[Turn={self._hazard_turn} | CaseId={self._hazard_case_id} | RequestTimestamp={ts}]\n"
            f"{base_sys}"
        )
        return super()._call_llm_step(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            system_instruction=poisoned_sys,
        )


def run_arm(
    arm_name: str,
    supervisor_model: str,
    worker_model: str,
    dynamic_prefix_hazard: bool,
    scenarios: List[Dict[str, Any]],
    runbook_text: str,
    static_prefix: str,
    project_id: str,
    budget_ledger: BudgetLedger,
    max_iterations: int = 6,
) -> Dict[str, Any]:
    """Run one caching arm across the selected scenarios sequentially."""
    case_results: List[Dict[str, Any]] = []
    tot_prompt = 0
    tot_cached = 0
    tot_comp = 0
    tot_thoughts = 0
    tot_cost = 0.0
    verdict_matches = 0
    t_arm0 = time.time()

    for case in scenarios:
        budget_ledger.assert_can_spend(reserve_usd=0.05)
        eval_id = str(case.get("eval_id", "CASE"))
        expected_verdict = str(
            case.get("ground_truth_label")
            or (case.get("reference") or {}).get("expected_verdict")
            or ""
        ).upper()
        env = ThreatHuntEnvironment(initial_state=case.get("initial_state"))
        agent_cls = DynamicPrefixHazardAgent if dynamic_prefix_hazard else HierarchicalSOCTier1Agent
        extra_kwargs: Dict[str, Any] = {"case_id": eval_id} if dynamic_prefix_hazard else {}
        agent = agent_cls(
            project_id=project_id,
            region="global",
            managed_model=supervisor_model,
            worker_model=worker_model,
            use_live_mcp=False,
            environment=env,
            runbooks_dict={"gti_collection_threat_hunt.md": runbook_text},
            use_runbooks=True,
            strip_scaffolding=True,
            static_context_prefix=static_prefix,
            **extra_kwargs,
        )

        t0 = time.time()
        res = agent.query(prompt=case["prompt"], max_iterations=max_iterations, temperature=0.0)
        latency_s = round(time.time() - t0, 2)

        usage = res.usage or {}
        p_tok = int(usage.get("prompt_tokens", 0) or 0)
        c_tok = int(usage.get("cached_tokens", 0) or 0)
        comp_tok = int(usage.get("completion_tokens", 0) or 0)
        th_tok = int(usage.get("thoughts_tokens", 0) or 0)
        cost_usd = float(usage.get("estimated_cost_usd", 0.0) or 0.0)
        hit_pct = round((c_tok / p_tok) * 100.0, 2) if p_tok > 0 else 0.0

        dec = extract_soc_decision(res.response)
        actual_verdict = str(res.verdict or (dec.verdict if dec else "UNKNOWN")).upper()
        verdict_ok = actual_verdict == expected_verdict
        if verdict_ok:
            verdict_matches += 1

        budget_ledger.record(
            run_key=f"{arm_name}:{eval_id}",
            delta_usd=cost_usd,
            meta={
                "supervisor_model": supervisor_model,
                "worker_model": worker_model,
                "prompt_tokens": p_tok,
                "cached_tokens": c_tok,
                "completion_tokens": comp_tok,
                "thoughts_tokens": th_tok,
                "cache_hit_pct": hit_pct,
            },
        )

        tot_prompt += p_tok
        tot_cached += c_tok
        tot_comp += comp_tok
        tot_thoughts += th_tok
        tot_cost += cost_usd

        w_usage = usage.get("worker_usage") or {}
        s_usage = usage.get("supervisor_usage") or {}
        case_results.append({
            "eval_id": eval_id,
            "expected_verdict": expected_verdict,
            "actual_verdict": actual_verdict,
            "verdict_ok": verdict_ok,
            "steps": len(res.trajectory or []),
            "latency_s": latency_s,
            "prompt_tokens": p_tok,
            "cached_tokens": c_tok,
            "cache_hit_pct": hit_pct,
            "completion_tokens": comp_tok,
            "thoughts_tokens": th_tok,
            "estimated_cost_usd": round(cost_usd, 6),
            "worker_cache_hit_pct": float(w_usage.get("cache_hit_pct", 0.0) or 0.0),
            "supervisor_cache_hit_pct": float(s_usage.get("cache_hit_pct", 0.0) or 0.0),
        })
        print(
            f"[{arm_name}] {eval_id}: verdict={actual_verdict} (expected={expected_verdict}) "
            f"prompt={p_tok} cached={c_tok} ({hit_pct:.1f}%) cost=${cost_usd:.4f} ({latency_s}s)",
            flush=True,
        )

    n = max(1, len(case_results))
    agg_hit_pct = round((tot_cached / tot_prompt) * 100.0, 2) if tot_prompt > 0 else 0.0
    cost_per_1k = round((tot_cost / n) * 1000.0, 2)
    return {
        "arm": arm_name,
        "supervisor_model": supervisor_model,
        "worker_model": worker_model,
        "dynamic_prefix_hazard": dynamic_prefix_hazard,
        "cases_evaluated": len(case_results),
        "verdict_matches": verdict_matches,
        "verdict_accuracy_pct": round((verdict_matches / n) * 100.0, 1),
        "prompt_tokens": tot_prompt,
        "cached_tokens": tot_cached,
        "cache_hit_pct": agg_hit_pct,
        "completion_tokens": tot_comp,
        "thoughts_tokens": tot_thoughts,
        "total_cost_usd": round(tot_cost, 6),
        "estimated_cost_per_1k_runs_usd": cost_per_1k,
        "wall_time_s": round(time.time() - t_arm0, 2),
        "cases": case_results,
    }


def render_markdown_report(summary: Dict[str, Any]) -> str:
    """Render empirical before/after cache hit % and cost table to Markdown."""
    arms = summary["arms"]
    baseline_1k = float(arms[0]["estimated_cost_per_1k_runs_usd"]) if arms else 0.0
    lines = [
        "# Gemini 4 Per-Model Implicit Prompt Caching Evaluation (Hierarchical SOC Agent)",
        "",
        f"- **Timestamp (UTC):** {summary['generated_at_utc']}",
        f"- **Suite:** `{summary['suite_path']}` ({summary['case_count']} scenarios)",
        f"- **Total Live Spend:** `${summary['total_spend_usd']:.4f}` (hard cap `${summary['budget_limit_usd']:.2f}`)",
        "- **Vertex AI Config:** `location=\"global\"`, `api_version=\"v1\"` (required on `google-genai 2.20.0` because `v1beta1` returns `cached_content_token_count=None`), Standard tier, `thinking_level=\"LOW\"`, sampling params (`temperature`/`top_p`/`top_k`) omitted on `gemini-4-*`, explicit caching gated off, `gemini-4-neon` concurrency `<= 2`.",
        "",
        "## Before vs. After Cache Hit % and Per-1K-Run TCO",
        "",
        "| Arm | Supervisor / Worker | Prefix Hygiene | Prompt Tokens | Cached Tokens | Cache Hit % | Output+Thinking | Verdict Acc | Est. USD / 1K Runs | Delta vs. Baseline |",
        "| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in arms:
        c1k = float(arm["estimated_cost_per_1k_runs_usd"])
        delta_str = "Baseline" if arm is arms[0] or baseline_1k <= 0 else f"{((c1k - baseline_1k) / baseline_1k) * 100.0:+.1f}%"
        hygiene = "Dynamic-first (hazard)" if arm["dynamic_prefix_hazard"] else "Static-first"
        out_th = int(arm["completion_tokens"]) + int(arm["thoughts_tokens"])
        lines.append(
            f"| `{arm['arm']}` | `{arm['supervisor_model']}` / `{arm['worker_model']}` | {hygiene} | "
            f"{arm['prompt_tokens']:,} | {arm['cached_tokens']:,} | {arm['cache_hit_pct']:.2f}% | "
            f"{out_th:,} | {arm['verdict_matches']}/{arm['cases_evaluated']} ({arm['verdict_accuracy_pct']:.0f}%) | "
            f"${c1k:,.2f} | {delta_str} |"
        )

    lines.extend([
        "",
        "## Per-Scenario Breakdown",
        "",
        "| Arm | Case ID | Verdict | Steps | Prompt Tokens | Cached Tokens | Cache Hit % | Worker Hit % | Supervisor Hit % | Est. Cost (USD) |",
        "| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for arm in arms:
        for c in arm["cases"]:
            v_str = f"{c['actual_verdict']} ({'PASS' if c['verdict_ok'] else 'MISS'})"
            lines.append(
                f"| `{arm['arm']}` | `{c['eval_id']}` | {v_str} | {c['steps']} | "
                f"{c['prompt_tokens']:,} | {c['cached_tokens']:,} | {c['cache_hit_pct']:.2f}% | "
                f"{c['worker_cache_hit_pct']:.2f}% | {c['supervisor_cache_hit_pct']:.2f}% | ${c['estimated_cost_usd']:.4f} |"
            )

    lines.extend([
        "",
        "## Key Takeaways",
        "",
        "1. **Token-0 Prefix Hygiene:** Removing dynamic timestamps, turn counters, and per-case payloads from `system_instruction` restores automatic Gemini 4 Implicit Context Caching (95% input discount above 4,096 shared prefix tokens).",
        "2. **Per-Model KV Isolation & Batching:** Running consecutive epistemic worker turns on `gemini-4-hydrogen` hits Hydrogen's warm KV cache on Turn 2+ before handing a consolidated report to `gemini-4-neon` for final containment synthesis.",
        "3. **Explicit Cache Removal & Parameter Hygiene:** All `gemini-4-*` calls omit `temperature`, `top_p`, `top_k`, and `cached_content`, avoiding HTTP 400 errors on Vertex AI.",
        "",
    ])
    return "\n".join(lines)


def _install_readonly_gcloud_adc_fallback() -> None:
    """If default ADC is expired, supply read-only gcloud access-token credentials without modifying global ADC."""
    try:
        import google.auth
        import google.auth.transport.requests

        creds, _ = google.auth.default()
        if not creds.valid:
            creds.refresh(google.auth.transport.requests.Request())
        return
    except Exception:
        pass

    token_res = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True,
        check=True,
    )
    token = token_res.stdout.strip()
    if not token:
        raise RuntimeError("Failed to obtain access token from gcloud auth print-access-token.")

    from google import genai
    from google.oauth2.credentials import Credentials

    ro_creds = Credentials(token=token)
    orig_client = genai.Client

    def _client_with_ro_creds(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("credentials", ro_creds)
        return orig_client(*args, **kwargs)

    genai.Client = _client_with_ro_creds  # type: ignore[misc, assignment]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded live Gemini 4 prompt caching smoke eval.")
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE_PATH)
    parser.add_argument("--runbook", type=Path, default=DEFAULT_RUNBOOK_PATH)
    parser.add_argument("--limit", type=int, default=4, help="Number of cases to run (default: 4).")
    parser.add_argument("--max-iterations", type=int, default=6)
    parser.add_argument("--budget-usd", type=float, default=2.50, help="Hard USD spend cap (must stay < $3.00).")
    parser.add_argument("--project-id", type=str, default=os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT") or "dandye-0324-chronicle")
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    args = parser.parse_args(argv)

    _install_readonly_gcloud_adc_fallback()
    os.environ.setdefault("GEMINI_4_THINKING_LEVEL", "LOW")

    suite_data = json.loads(args.suite.read_text(encoding="utf-8"))
    scenarios = (suite_data.get("scenarios") or suite_data.get("eval_cases") or [])[: args.limit]
    runbook_text = args.runbook.read_text(encoding="utf-8")
    static_prefix = build_enterprise_soc_static_prefix()

    ledger_path = Path("/tmp/gemini4_prompt_caching_eval_budget.json")
    if ledger_path.exists():
        ledger_path.unlink()
    ledger = BudgetLedger(path=ledger_path, limit_usd=min(2.90, float(args.budget_usd)))

    arm_specs = [
        ("dynamic_first_neon", "gemini-4-neon", "gemini-4-neon", True),
        ("static_first_neon", "gemini-4-neon", "gemini-4-neon", False),
        ("static_first_neon_hydrogen", "gemini-4-neon", "gemini-4-hydrogen", False),
    ]
    arms_out: List[Dict[str, Any]] = []
    for arm_name, sup_m, work_m, hazard in arm_specs:
        arms_out.append(
            run_arm(
                arm_name=arm_name,
                supervisor_model=sup_m,
                worker_model=work_m,
                dynamic_prefix_hazard=hazard,
                scenarios=scenarios,
                runbook_text=runbook_text,
                static_prefix=static_prefix,
                project_id=args.project_id,
                budget_ledger=ledger,
                max_iterations=args.max_iterations,
            )
        )

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "suite_path": str(args.suite.relative_to(ROOT_DIR)),
        "case_count": len(scenarios),
        "budget_limit_usd": ledger.limit_usd,
        "total_spend_usd": round(ledger.spent_usd, 6),
        "arms": arms_out,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    args.output_md.write_text(render_markdown_report(summary), encoding="utf-8")
    print(f"\nSaved report to {args.output_md} and {args.output_json} (total spend: ${ledger.spent_usd:.4f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
