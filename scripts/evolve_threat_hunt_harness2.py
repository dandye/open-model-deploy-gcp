#!/usr/bin/env python3
"""Recursive Harness^2 (INV/DOM Propose-Probe-Compose) Optimizer for Track 2 Threat Hunting.

Evolves `configs/runbooks/gti_collection_threat_hunt.md` against `ThreatHuntEnvironment`
(`configs/evals/hunt/ursnif_gti_hunt_suite.json`) with:
  - Scoped INVARIANT (INV) and DOMAIN (DOM) editors via `Harness2ProposeProbeComposeProposer`
  - Categorical inner-probe and post-round acceptance gates (`evaluate_candidate_acceptance`)
  - 4-state component attribution (`helped | hurt | no_observed_effect | confounded`)
  - Continual improvement library (`EXPERIENCE.md` and `experience_library.jsonl`)
  - Anti-memorization validation forbidding campaign-specific literals
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import gepa
from agent.aqua_diagnostics import sanitize_payload
from agent.gepa_runbook_optimizer import (
    GoogleGenAILM,
    Harness2ProposeProbeComposeProposer,
    WordLimitReflectionLM,
    summarize_runbook_diff_lesson,
    validate_runbook_candidate,
)
from agent.hierarchical_soc_agent import (
    HierarchicalSOCTier1Agent,
    strip_runbook_scaffolding,
)
from agent.hillclimb_harness import (
    BudgetLedger,
    ExperienceLibrary,
    HillclimbLedger,
    attribute_candidate_edits,
    evaluate_candidate_acceptance,
)
from agent.soc_tier1_agent import extract_soc_decision
from agent.threat_hunt_environment import (
    BENIGN_NGINX_HTML_SHA256,
    LOLBIN_RUNDLL32_SHA256,
    PATIENT_ZERO_HOST,
    ThreatHuntEnvironment,
    UNALERTED_SOAR_CASE_ID,
    URSNIF_C2_IP,
    URSNIF_COLLECTION_ID,
    URSNIF_DLL_SHA256,
    URSNIF_PAYLOAD_SHA256,
    URSNIF_PRIMARY_C2_DOMAIN,
    URSNIF_REPORT_ID,
)
from scripts.eval_threat_hunt_multi_model import (
    COMPRESSED_TRACK_B_HUNT_PATH,
    DEFAULT_SUITE_PATH,
    analyze_hunt_trajectory,
)
from scripts.verify_harbor_soc import compose_soc_reward

HUNT_COMPONENT_NAME = "gti_collection_threat_hunt.md"

HUNT_FORBIDDEN_LITERALS: List[str] = [
    URSNIF_COLLECTION_ID,
    URSNIF_REPORT_ID,
    URSNIF_PRIMARY_C2_DOMAIN,
    "superliner.top",
    "internetlined.com",
    "superlinez.top",
    "denterdrigx.com",
    "internetlines.in",
    URSNIF_C2_IP,
    URSNIF_PAYLOAD_SHA256,
    URSNIF_DLL_SHA256,
    LOLBIN_RUNDLL32_SHA256,
    BENIGN_NGINX_HTML_SHA256,
    PATIENT_ZERO_HOST,
    "SRV-PROD-PAYMENT-01",
    UNALERTED_SOAR_CASE_ID,
    "CASE-4102",
    "CASE-5039",
    "CHG-88412",
    "itsIt.db",
    "gift_unwrap.js",
]


def build_hunt_inv_prompt_template() -> str:
    """Build INVARIANT (INV) reflection prompt for Track 2 proactive threat hunting."""
    return (
        "You are the INVARIANT (INV) agent harness editor in a Harness^2 Propose-Probe-Compose loop\n"
        "for Track 2 Proactive Threat Hunting (`gti_collection_threat_hunt.md`).\n"
        "Your scope is strictly cross-domain agentic workflow, multi-horizon lookback sequencing,\n"
        "degraded service-outage fallback handling, and compact runbook structure.\n\n"
        "Active Runbook Component:\n"
        "```markdown\n"
        "<curr_param>\n"
        "```\n\n"
        "Diagnostic Traces & Prior Experience:\n"
        "```\n"
        "<side_info>\n"
        "```\n\n"
        "INV Editor Rules:\n"
        "1. Preserve the 6-section markdown skeleton (`# Proactive GTI Collection & Campaign Threat Hunt`, `## Objective`, `## Scope`, `## Inputs`, `## Tools`, `## Workflow Steps` with `### Stage A`, `### Stage B`, `### Stage C`).\n"
        "2. Inspect `<side_info>` for workflow sequencing gaps (such as missing lookback horizon widening when initial SIEM queries return empty, or missing SOAR case correlation during upstream service outages) and refine the stage ordering to address them.\n"
        "3. Keep total length <= 320 words, use `<angle_bracket>` input slots (never `${VAR_NAME}`), never include Mermaid blocks or interactive pseudo-tools, never hardcode campaign domains/hashes/hostnames/CASE IDs, and never use emojis.\n\n"
        "Provide the complete revised runbook inside ```markdown blocks."
    )


def build_hunt_dom_prompt_template() -> str:
    """Build DOMAIN (DOM) reflection prompt for Track 2 proactive threat hunting."""
    return (
        "You are the DOMAIN (DOM) SecOps threat-hunting editor in a Harness^2 Propose-Probe-Compose loop\n"
        "for Track 2 Proactive Threat Hunting (`gti_collection_threat_hunt.md`).\n"
        "Your scope is strictly CTI graph pivoting, file reputation and digital signature verification,\n"
        "CMDB change-window verification, and 4-way verdict containment safety.\n\n"
        "Active Runbook Component:\n"
        "```markdown\n"
        "<curr_param>\n"
        "```\n\n"
        "Diagnostic Traces & Prior Experience:\n"
        "```\n"
        "<side_info>\n"
        "```\n\n"
        "DOM Editor Rules:\n"
        "1. Preserve the 6-section markdown skeleton (`# Proactive GTI Collection & Campaign Threat Hunt`, `## Objective`, `## Scope`, `## Inputs`, `## Tools`, `## Workflow Steps` with `### Stage A`, `### Stage B`, `### Stage C`).\n"
        "2. Inspect `<side_info>` for domain verification gaps (such as unverified file hashes from second-hop domain pivots, unverified certificate status on OS binaries, or missing CMDB/SOAR correlation) and tighten the Stage B/C domain contracts accordingly.\n"
        "3. Preserve the 4-way verdict disposition matrix (`MALICIOUS`, `SUSPICIOUS`, `INCONCLUSIVE`, `BENIGN`) and containment safety constraints.\n"
        "4. Keep total length <= 320 words, use `<angle_bracket>` input slots (never `${VAR_NAME}`), never hardcode campaign domains/hashes/hostnames/CASE IDs, and never use emojis.\n\n"
        "Provide the complete revised runbook inside ```markdown blocks."
    )


class ThreatHuntGEPAAdapter:
    """Adapter evaluating `gti_collection_threat_hunt.md` candidates on `ThreatHuntEnvironment`."""

    def __init__(
        self,
        task_lm: str = "gemini-2.5-flash-lite",
        project_id: Optional[str] = None,
        region: str = "us-central1",
        seed_candidate: Optional[Dict[str, str]] = None,
        max_growth_ratio: float = 1.35,
        forbidden_literals: Optional[Sequence[str]] = None,
        max_words: Optional[int] = 350,
        max_iterations: int = 8,
        budget_ledger: Optional[BudgetLedger] = None,
    ) -> None:
        self.task_lm = task_lm
        self.project_id = project_id
        self.region = region
        self.seed_candidate = dict(seed_candidate or {})
        self.max_growth_ratio = max_growth_ratio
        self.forbidden_literals = list(forbidden_literals or HUNT_FORBIDDEN_LITERALS)
        self.max_words = max_words
        self.max_iterations = max_iterations
        self.budget_ledger = budget_ledger
        self._telemetry_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def _cand_key(self, candidate: Mapping[str, str]) -> str:
        return json.dumps(dict(candidate), sort_keys=True)

    def get_cached_telemetry(
        self,
        candidate: Mapping[str, str],
        batch: Optional[Sequence[Mapping[str, Any]]] = None,
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        ck = self._cand_key(candidate)
        cached = self._telemetry_cache.get(ck)
        if not cached:
            return None
        if batch is None:
            return dict(cached)
        sub: Dict[str, Dict[str, Any]] = {}
        for idx, c in enumerate(batch):
            cid = str(c.get("eval_id") or c.get("case_id") or f"hunt-{idx}")
            if cid in cached:
                sub[cid] = cached[cid]
        return sub if len(sub) == len(batch) else None

    def evaluate(
        self,
        batch: Sequence[Mapping[str, Any]],
        candidate: Dict[str, str],
        capture_traces: bool = False,
    ) -> gepa.EvaluationBatch:
        is_seed = (candidate == self.seed_candidate)
        ok, violations = validate_runbook_candidate(
            candidate,
            seed_candidate=self.seed_candidate,
            max_growth_ratio=self.max_growth_ratio,
            forbidden_literals=self.forbidden_literals,
            forbid_template_vars=not is_seed,
            forbid_mermaid_diagrams=not is_seed,
            forbid_interactive_pseudotools=not is_seed,
            max_words=self.max_words if not is_seed else None,
        )
        if not ok:
            zero_trajs = [
                {
                    "case_id": str(c.get("eval_id") or f"hunt-{i}"),
                    "component_name": HUNT_COMPONENT_NAME,
                    "score": 0.0,
                    "loss_penalty": 0.0,
                    "assert_passed": False,
                    "safety_gate_triggered": False,
                    "zero_tool_hesitation": False,
                    "inert": False,
                    "failure_category": "RUNBOOK_PROCEDURAL_VIOLATION",
                    "violations": violations,
                }
                for i, c in enumerate(batch)
            ]
            return gepa.EvaluationBatch(
                outputs=["INVALID_RUNBOOK" for _ in batch],
                scores=[0.0 for _ in batch],
                trajectories=zero_trajs if capture_traces else None,
            )

        ck = self._cand_key(candidate)
        self._telemetry_cache.setdefault(ck, {})

        outputs: List[str] = []
        scores: List[float] = []
        trajectories: List[Dict[str, Any]] = []

        for idx, raw_case in enumerate(batch):
            case = dict(raw_case)
            cid = str(case.get("eval_id") or case.get("case_id") or f"hunt-{idx}")
            if cid in self._telemetry_cache[ck]:
                cached_t = self._telemetry_cache[ck][cid]
                outputs.append(str(cached_t.get("summary", "")))
                scores.append(float(cached_t.get("score", 0.0)))
                trajectories.append(dict(cached_t))
                continue

            env = ThreatHuntEnvironment(initial_state=case.get("initial_state"))
            agent = HierarchicalSOCTier1Agent(
                project_id=self.project_id,
                region=self.region,
                managed_model=self.task_lm,
                use_live_mcp=False,
                environment=env,
                runbooks_dict={HUNT_COMPONENT_NAME: candidate[HUNT_COMPONENT_NAME]},
                use_runbooks=True,
                strip_scaffolding=True,
            )
            res = agent.query(
                prompt=case["prompt"],
                max_iterations=self.max_iterations,
                temperature=0.0,
            )
            if self.budget_ledger is not None:
                usage = res.usage or {}
                in_tok = int(usage.get("prompt_tokens", 0) or 0)
                out_tok = int(usage.get("completion_tokens", 0) or 0)
                self.budget_ledger.record(
                    run_key=f"hunt:{self.task_lm}:{cid}",
                    model=self.task_lm,
                    prompt_tokens=in_tok,
                    completion_tokens=out_tok,
                    meta={"model": self.task_lm, "case_id": cid},
                )

            dec_obj = extract_soc_decision(res.response)
            actual_verdict = str(
                getattr(dec_obj, "verdict", None) or res.verdict or "UNKNOWN"
            ).upper()
            dec_dict = {
                "verdict": actual_verdict,
                "recommended_actions": getattr(dec_obj, "recommended_actions", None) or [],
                "target_entity": getattr(dec_obj, "target_entity", None),
            }
            harbor_info = compose_soc_reward(
                case=case,
                trajectory=res.trajectory,
                report_text=res.response,
                decision_data=dec_dict,
                jev_backend_name="mock",
            )
            hunt_metrics = analyze_hunt_trajectory(
                case=case,
                trajectory=res.trajectory,
                report_text=res.response,
                actual_verdict=actual_verdict,
                harbor_breakdown=harbor_info,
            )
            harbor_reward = float(harbor_info.get("reward", 0.0))
            hunt_comp = float(hunt_metrics["hunt_composite_score"])
            combined_score = round(0.50 * hunt_comp + 0.50 * harbor_reward, 6)

            epistemic_steps = sum(
                1 for s in res.trajectory if s.get("agent") == "worker" and s.get("tool")
            )
            safety_gate = bool(harbor_info.get("safety_gate_triggered", False))
            inert = bool(harbor_info.get("inert", False))
            zero_tools = epistemic_steps == 0 and not inert

            is_outage_case = (
                str(case.get("ground_truth_label", "")).upper() == "INCONCLUSIVE"
                or any("503" in str(s.get("observation", "")) for s in res.trajectory)
            )
            if safety_gate:
                failure_cat = "OVER_CONTAINMENT_FALSE_ALARM"
            elif zero_tools:
                failure_cat = "PREMATURE_TERMINATION_ZERO_TOOLS"
            elif is_outage_case and combined_score < 0.90:
                failure_cat = "DEGRADED_MODE_FAILURE"
            elif combined_score < 0.90:
                failure_cat = "RUNBOOK_PROCEDURAL_VIOLATION"
            else:
                failure_cat = "FLAWLESS_CONTAINMENT"

            traj_record: Dict[str, Any] = {
                "case_id": cid,
                "eval_id": cid,
                "component_name": HUNT_COMPONENT_NAME,
                "alert_type": "THREAT_HUNT",
                "prompt": case["prompt"],
                "expected_verdict": case["ground_truth_label"],
                "actual_verdict": actual_verdict,
                "expected_actions": list(case.get("expected_actions", [])),
                "prohibited_actions": list(case.get("prohibited_actions", [])),
                "executed_actions": list(hunt_metrics["executed_actions"]),
                "score": combined_score,
                "hunt_composite_score": hunt_comp,
                "harbor_reward": harbor_reward,
                "loss_penalty": 0.0 if safety_gate else 1.0,
                "assert_passed": combined_score >= 0.90 and not safety_gate,
                "safety_gate_triggered": safety_gate,
                "zero_tool_hesitation": zero_tools,
                "inert": inert,
                "tool_calls": len(res.trajectory),
                "epistemic_steps": epistemic_steps,
                "failure_category": failure_cat,
                "hunt_metrics": hunt_metrics,
                "summary": res.response[:600],
                "trajectory": res.trajectory,
                "usage": res.usage,
            }
            self._telemetry_cache[ck][cid] = traj_record
            outputs.append(res.response)
            scores.append(combined_score)
            trajectories.append(traj_record)

        return gepa.EvaluationBatch(
            outputs=outputs,
            scores=scores,
            trajectories=trajectories if capture_traces else None,
        )

    def make_reflective_dataset(
        self,
        candidate: Dict[str, str],
        eval_batch: gepa.EvaluationBatch,
        components_to_update: List[str],
    ) -> Dict[str, List[Dict[str, Any]]]:
        dataset: Dict[str, List[Dict[str, Any]]] = {c: [] for c in components_to_update}
        if HUNT_COMPONENT_NAME not in dataset:
            return dataset
        trajs = list(eval_batch.trajectories or [])
        for t in trajs:
            hm = t.get("hunt_metrics") or {}
            fb_parts: List[str] = []
            is_degraded_outage = (
                str(t.get("expected_verdict", "")).upper() == "INCONCLUSIVE"
                or t.get("failure_category") == "DEGRADED_MODE_FAILURE"
            )
            if not hm.get("verdict_ok", True):
                fb_parts.append(
                    f"Verdict mismatch: expected {t.get('expected_verdict')}, got {t.get('actual_verdict')}."
                )
            if not hm.get("operator_ok", True):
                fb_parts.append(
                    f"Missing required SOAR/containment actions: expected {t.get('expected_actions')}, executed {t.get('executed_actions')}."
                )
            if not hm.get("widened_168h", True) and not is_degraded_outage:
                fb_parts.append(
                    "Did not widen SIEM lookback from 72h to 168h when 72h returned 0 hits."
                )
            if not hm.get("verified_lolbin_hash", True) and not is_degraded_outage:
                fb_parts.append(
                    "Did not call get_file_report on all candidate file hashes to verify certificate status before containment."
                )
            if float(t.get("harbor_reward", 1.0)) < 0.99 and not is_degraded_outage:
                fb_parts.append(
                    f"Incomplete entity/action coverage (harbor_reward={float(t.get('harbor_reward', 0.0)):.4f})."
                )
            if float(t.get("score", 1.0)) < 0.995 or fb_parts:
                raw_rec = {
                    "Inputs": {
                        "case_id": t.get("case_id", ""),
                        "alert_type": "THREAT_HUNT",
                        "prompt": t.get("prompt", ""),
                        "expected_verdict": t.get("expected_verdict", ""),
                        "expected_actions": t.get("expected_actions", []),
                        "prohibited_actions": t.get("prohibited_actions", []),
                    },
                    "Generated Outputs": {
                        "actual_verdict": t.get("actual_verdict", ""),
                        "executed_actions": t.get("executed_actions", []),
                        "hunt_composite_score": t.get("hunt_composite_score", 0.0),
                        "harbor_reward": t.get("harbor_reward", 0.0),
                    },
                    "Feedback": " ".join(fb_parts) or "All scenario checks passed.",
                }
                dataset[HUNT_COMPONENT_NAME].append(
                    sanitize_payload(raw_rec, forbidden_literals=self.forbidden_literals)
                )
        return dataset


def run_threat_hunt_harness2_evolution(
    suite_path: Path = DEFAULT_SUITE_PATH,
    seed_runbook_path: Path = COMPRESSED_TRACK_B_HUNT_PATH,
    output_dir: Path = ROOT_DIR / "docs" / "soc_eval_results" / "harness2_8h_campaign" / "threat_hunt",
    task_lm: str = "gemini-2.5-flash-lite",
    reflection_lm_name: str = "gemini-2.5-pro",
    rounds: int = 2,
    max_words: int = 350,
    tau_accept: float = 0.010,
    budget_limit_usd: float = 2.50,
    project_id: Optional[str] = None,
    region: str = "us-central1",
    reflection_lm_override: Optional[Callable[[Any], str]] = None,
    adapter_override: Optional[ThreatHuntGEPAAdapter] = None,
) -> Dict[str, Any]:
    """Runs k-round Harness^2 evolution on `gti_collection_threat_hunt.md`."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    suite_data = json.loads(Path(suite_path).read_text(encoding="utf-8"))
    scenarios = list(suite_data.get("scenarios", []))
    raw_seed_text = Path(seed_runbook_path).read_text(encoding="utf-8")
    seed_candidate = {
        HUNT_COMPONENT_NAME: strip_runbook_scaffolding(
            raw_seed_text, normalize_template_vars=True
        )
    }

    budget_ledger = BudgetLedger(
        output_dir / "budget_ledger.json",
        limit_usd=float(budget_limit_usd),
    )
    adapter = adapter_override or ThreatHuntGEPAAdapter(
        task_lm=task_lm,
        project_id=project_id,
        region=region,
        seed_candidate=seed_candidate,
        max_words=max_words,
        budget_ledger=budget_ledger,
    )

    if reflection_lm_override is not None:
        reflection_lm: Any = reflection_lm_override
    else:
        base_lm = GoogleGenAILM(
            model=reflection_lm_name,
            project_id=project_id,
            location=region,
        )
        reflection_lm = WordLimitReflectionLM(
            base_lm,
            max_words=max_words,
            forbid_template_vars=True,
            forbid_mermaid_diagrams=True,
            forbid_interactive_pseudotools=True,
            budget_ledger=budget_ledger,
            model_name=reflection_lm_name,
        )

    experience_library = ExperienceLibrary(output_dir)
    ledger = HillclimbLedger(output_dir / "hillclimb_ledger.jsonl")

    class ThreatHuntProposer(Harness2ProposeProbeComposeProposer):
        def _validate_component_candidate(
            self,
            candidate: Dict[str, str],
            comp_name: str,
            new_text: str,
        ) -> bool:
            ok = super()._validate_component_candidate(candidate, comp_name, new_text)
            if not ok:
                _, v = validate_runbook_candidate(
                    {comp_name: new_text},
                    seed_candidate=self.seed_candidate,
                    max_growth_ratio=self.max_growth_ratio,
                    forbidden_literals=self.forbidden_literals,
                    forbid_template_vars=self.forbid_template_vars,
                    forbid_mermaid_diagrams=self.forbid_mermaid_diagrams,
                    forbid_interactive_pseudotools=self.forbid_interactive_pseudotools,
                    max_words=self.max_words,
                )
                print(f"[ThreatHuntProposer] Validation rejected candidate for {comp_name}: {v}", flush=True)
            return ok

    proposer = ThreatHuntProposer(
        reflection_lm=reflection_lm,
        probe_adapter=adapter,
        probe_batch=scenarios,
        probe_limit=len(scenarios),
        experience_library=experience_library,
        seed_candidate=seed_candidate,
        max_growth_ratio=1.35,
        forbidden_literals=HUNT_FORBIDDEN_LITERALS,
        forbid_template_vars=True,
        forbid_mermaid_diagrams=True,
        forbid_interactive_pseudotools=True,
        max_words=max_words,
        inv_prompt_template=build_hunt_inv_prompt_template(),
        dom_prompt_template=build_hunt_dom_prompt_template(),
    )

    # Evaluate baseline seed
    base_batch = adapter.evaluate(scenarios, seed_candidate, capture_traces=True)
    base_trajs = list(base_batch.trajectories or [])
    baseline_subscores = {
        str(t["case_id"]): float(t["score"]) for t in base_trajs
    }
    baseline_telemetry = {
        str(t["case_id"]): dict(t) for t in base_trajs
    }
    base_mean = sum(baseline_subscores.values()) / max(1, len(baseline_subscores))

    ledger.append_entry(
        iteration=0,
        harness_sha256="track2-threat-hunt",
        train_score=base_mean,
        val_score=base_mean,
        tau_accept=tau_accept,
        decision="KEPT",
        rationale="Track 2 threat-hunt seed baseline.",
        metadata={
            "task_lm": task_lm,
            "proposal_mode": "harness2",
            "round": 0,
            "subscores": baseline_subscores,
        },
    )

    best_candidate = dict(seed_candidate)
    best_score = base_mean
    best_eval_batch = base_batch
    selected_round = 0
    round_records: List[Dict[str, Any]] = []

    for r_idx in range(1, max(1, int(rounds)) + 1):
        refl_data = adapter.make_reflective_dataset(
            best_candidate,
            best_eval_batch,
            [HUNT_COMPONENT_NAME],
        )
        proposed_map = proposer(
            best_candidate,
            refl_data,
            [HUNT_COMPONENT_NAME],
        )
        cand = {HUNT_COMPONENT_NAME: proposed_map.get(HUNT_COMPONENT_NAME, best_candidate[HUNT_COMPONENT_NAME])}
        cand_batch = adapter.evaluate(scenarios, cand, capture_traces=True)
        cand_trajs = list(cand_batch.trajectories or [])
        cand_subscores = {
            str(t["case_id"]): float(t["score"]) for t in cand_trajs
        }
        cand_telemetry = {
            str(t["case_id"]): dict(t) for t in cand_trajs
        }
        cand_mean = sum(cand_subscores.values()) / max(1, len(cand_subscores))

        acc = evaluate_candidate_acceptance(
            baseline_scores=baseline_subscores,
            candidate_scores=cand_subscores,
            tau_accept=tau_accept,
            baseline_telemetry=baseline_telemetry,
            candidate_telemetry=cand_telemetry,
        )
        attributions = attribute_candidate_edits(
            base_candidate=seed_candidate,
            candidate=cand,
            baseline_scores=baseline_subscores,
            candidate_scores=cand_subscores,
            tau_accept=tau_accept,
            baseline_telemetry=baseline_telemetry,
            candidate_telemetry=cand_telemetry,
        )
        attr_map = {k: v.label for k, v in attributions.items()}

        ledger.append_entry(
            iteration=r_idx,
            harness_sha256="track2-threat-hunt",
            train_score=cand_mean,
            val_score=cand_mean,
            tau_accept=tau_accept,
            decision=acc.status,
            rationale=acc.reason,
            metadata={
                "task_lm": task_lm,
                "proposal_mode": "harness2",
                "round": r_idx,
                "subscores": cand_subscores,
                "component_attributions": attr_map,
                "probe_record": proposer.last_probe_records[-1] if proposer.last_probe_records else None,
            },
        )

        last_probe = proposer.last_probe_records[-1] if proposer.last_probe_records else None
        selected_scope = (
            str(last_probe.get("selected_scope"))
            if isinstance(last_probe, Mapping) and last_probe.get("selected_scope") in ("INV", "DOM", "COMPOSED")
            else "COMPOSED"
        )
        if attr_map.get(HUNT_COMPONENT_NAME) == "helped" and cand != best_candidate:
            experience_library.record_from_attributions(
                attributions=attributions,
                cue=f"Track 2 Threat Hunt refinement (round {r_idx})",
                lesson=summarize_runbook_diff_lesson(
                    component_name=HUNT_COMPONENT_NAME,
                    base_text=best_candidate.get(HUNT_COMPONENT_NAME, ""),
                    new_text=cand.get(HUNT_COMPONENT_NAME, ""),
                    mean_delta=cand_mean - base_mean,
                ),
                evidence=f"Round {r_idx} ({selected_scope}) evaluated across {len(scenarios)} Ursnif GTI hunt scenarios.",
                scope=selected_scope,
            )

        if acc.accepted and cand_mean > best_score:
            best_candidate = dict(cand)
            best_score = cand_mean
            best_eval_batch = cand_batch
            selected_round = r_idx

        round_records.append({
            "round": r_idx,
            "val_score": cand_mean,
            "decision": acc.status,
            "attribution": attr_map.get(HUNT_COMPONENT_NAME),
            "subscores": cand_subscores,
        })

    promoted = selected_round > 0
    out_runbook_path = output_dir / HUNT_COMPONENT_NAME
    out_runbook_path.write_text(best_candidate[HUNT_COMPONENT_NAME], encoding="utf-8")

    metadata = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "task_lm": task_lm,
        "reflection_lm": reflection_lm_name,
        "rounds": rounds,
        "baseline_score": round(base_mean, 6),
        "best_score": round(best_score, 6),
        "delta": round(best_score - base_mean, 6),
        "promoted": promoted,
        "selected_round": selected_round,
        "baseline_subscores": baseline_subscores,
        "round_records": round_records,
        "probe_records": proposer.last_probe_records,
    }
    (output_dir / "evolution_metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evolve Track 2 gti_collection_threat_hunt.md runbook via Harness^2."
    )
    parser.add_argument("--task-lm", default="gemini-2.5-flash-lite")
    parser.add_argument("--reflection-lm", default="gemini-2.5-pro")
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--max-words", type=int, default=350)
    parser.add_argument("--tau-accept", type=float, default=0.010)
    parser.add_argument("--budget-limit-usd", type=float, default=2.50)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT_DIR / "docs" / "soc_eval_results" / "harness2_8h_campaign" / "threat_hunt",
    )
    args = parser.parse_args()

    project_id = (
        os.environ.get("PROJECT_ID")
        or os.environ.get("GCP_PROJECT_ID")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or None
    )
    meta = run_threat_hunt_harness2_evolution(
        output_dir=args.output_dir,
        task_lm=args.task_lm,
        reflection_lm_name=args.reflection_lm,
        rounds=args.rounds,
        max_words=args.max_words,
        tau_accept=args.tau_accept,
        budget_limit_usd=args.budget_limit_usd,
        project_id=project_id,
    )
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
