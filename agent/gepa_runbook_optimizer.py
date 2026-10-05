"""GEPA (Genetic Engine for Prompt Ad-hoc Optimization) for Incident Response Runbooks.

This module provides data structures, seed runbook loaders, serialization utilities,
and multi-objective fitness metrics for evolving cybersecurity incident response runbooks.
"""

import argparse
from collections.abc import Mapping, Sequence
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import gepa

try:
    from agent.hierarchical_soc_agent import HierarchicalSOCTier1Agent
    from agent.hillclimb_harness import (
        DEFAULT_COST_STAIRCASE_TIERS,
        DEFAULT_PROTECTED_HARNESS_PATHS,
        HarnessIntegrityGuard,
        HarnessTamperError,
        HillclimbLedger,
        estimate_noise_floor,
        evaluate_candidate_acceptance,
        run_cost_staircase_walk,
        write_noise_floor_json,
    )
    from agent.jev_backend_gemini import GeminiSystem1Backend
    from agent.jev_evaluator import JevSocJudgeEvaluator
    from agent.jev_judge import MockJevBackend
    from agent.soc_environment import SocEnvironment
    from agent.soc_tier1_agent import extract_soc_decision
except ModuleNotFoundError:
    from hierarchical_soc_agent import HierarchicalSOCTier1Agent
    from hillclimb_harness import (
        DEFAULT_COST_STAIRCASE_TIERS,
        DEFAULT_PROTECTED_HARNESS_PATHS,
        HarnessIntegrityGuard,
        HarnessTamperError,
        HillclimbLedger,
        estimate_noise_floor,
        evaluate_candidate_acceptance,
        run_cost_staircase_walk,
        write_noise_floor_json,
    )
    from jev_backend_gemini import GeminiSystem1Backend
    from jev_evaluator import JevSocJudgeEvaluator
    from jev_judge import MockJevBackend
    from soc_environment import SocEnvironment
    from soc_tier1_agent import extract_soc_decision

from scripts import gen5_exposure
from scripts.eval_soc_agent import evaluate_assertions
from scripts.eval_trajectory_verifier import verify_agent_trajectory
DEFAULT_RUNBOOKS_DIR = (
    ROOT_DIR / "third_party" / "ai-runbooks" / ".clinerules" / "run_books"
)

CORE_RUNBOOKS: List[str] = [
    "basic_ioc_enrichment.md",
    "suspicious_login_triage.md",
    "malware_triage.md",
    "lateral_movement_hunt_psexec_wmi.md",
]


def load_seed_runbooks(
    runbooks_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, str]:
    """Load the core seed runbooks from disk.

    Args:
        runbooks_dir: Path to directory containing runbooks. Defaults to DEFAULT_RUNBOOKS_DIR.

    Returns:
        Dict mapping runbook filename to markdown string content.

    Raises:
        FileNotFoundError: If any core runbook file is missing.
    """
    source_dir = Path(runbooks_dir) if runbooks_dir is not None else DEFAULT_RUNBOOKS_DIR

    candidate: Dict[str, str] = {}
    for runbook_name in CORE_RUNBOOKS:
        file_path = source_dir / runbook_name
        if not file_path.exists():
            raise FileNotFoundError(
                f"Core runbook {runbook_name} not found in directory: {source_dir}"
            )
        candidate[runbook_name] = file_path.read_text(encoding="utf-8")

    return candidate


def save_runbooks(
    candidate: Dict[str, str],
    output_dir: Union[str, Path],
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Write candidate runbooks and optional evolution metadata to output directory.

    Args:
        candidate: Dict mapping runbook filename to markdown content.
        output_dir: Directory where runbooks and metadata should be written.
        metadata: Optional metadata dictionary saved as evolution_metadata.json.
    """
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    for filename, content in candidate.items():
        file_path = target_dir / filename
        file_path.write_text(content, encoding="utf-8")

    if metadata is not None:
        meta_path = target_dir / "evolution_metadata.json"
        meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def write_evolution_metadata(output_dir: Path, metadata: Dict[str, Any]) -> Path:
    """Writes evolution_metadata.json without touching any runbook file."""
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    meta_path = target_dir / "evolution_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return meta_path


def select_candidate_outcome(selected_index: Optional[int], valid_count: int) -> Tuple[str, bool]:
    """(selection_reason, write_runbooks). Only a non-seed winner is ever written to disk."""
    if selected_index is not None and selected_index > 0:
        return "highest_valid_validation_score", True
    if valid_count > 0:
        return "seed_retained_all_candidates_reverted", False
    return "seed_fallback_no_valid_candidates", False


def calculate_loss_penalty(
    expected_label: str,
    actual_verdict: str,
    executed_actions: List[str],
    prohibited_actions: List[str],
    prohibited_violation: Optional[bool] = None,
) -> float:
    """Calculate operational loss penalty score.

    Penalizes prohibited actions and classification errors:
    - If prohibited action executed: +10000.0 loss
    - If mutating action against prohibited entity executed: +10000.0 loss
    - If false positive (verdict MALICIOUS when expected BENIGN): +5000.0 loss
    - If false negative (verdict BENIGN when expected MALICIOUS): +10000.0 loss

    Score formula: exp(-loss / 10000.0)

    Args:
        expected_label: Expected ground truth label (BENIGN or MALICIOUS).
        actual_verdict: Actual model triage verdict (BENIGN, MALICIOUS, SUSPICIOUS, etc.).
        executed_actions: List of action names executed by agent.
        prohibited_actions: List of prohibited action names for this case.
        prohibited_violation: Optional boolean indicating a mutating action against a prohibited entity.

    Returns:
        Penalty score between 0.0 and 1.0 (1.0 = zero loss).
    """
    loss = 0.0

    prohibited_set = set(prohibited_actions or [])
    if any(action in prohibited_set for action in (executed_actions or [])):
        loss += 10000.0

    if prohibited_violation:
        # Gen 5: a mutating action against a prohibited entity weighs the same as a prohibited action.
        loss += 10000.0

    norm_expected = (expected_label or "").strip().upper()
    norm_actual = (actual_verdict or "").strip().upper()

    if norm_actual == "MALICIOUS" and norm_expected == "BENIGN":
        loss += 5000.0
    elif norm_actual == "BENIGN" and norm_expected == "MALICIOUS":
        loss += 10000.0

    return math.exp(-loss / 10000.0)


def calculate_case_fitness(
    rubric_score: float,
    assertions_passed: bool,
    operator_compliance: float,
    loss_penalty: float,
) -> float:
    """Calculate multi-objective case fitness score.

    Formula:
        0.40 * rubric_score + 0.20 * (1.0 if assertions_passed else 0.0)
        + 0.20 * operator_compliance + 0.20 * loss_penalty

    Args:
        rubric_score: Normalized rubric score between 0.0 and 1.0.
        assertions_passed: Boolean indicating whether all deterministic assertions passed.
        operator_compliance: Normalized compliance score between 0.0 and 1.0.
        loss_penalty: Loss penalty score between 0.0 and 1.0.

    Returns:
        Weighted composite fitness score.
    """
    assert_score = 1.0 if assertions_passed else 0.0
    fitness = (
        0.40 * float(rubric_score)
        + 0.20 * assert_score
        + 0.20 * float(operator_compliance)
        + 0.20 * float(loss_penalty)
    )
    return fitness


class GoogleGenAILM:
    """LanguageModel implementation using Google GenAI SDK for GEPA reflective mutation."""

    def __init__(
        self,
        model: str = "gemini-2.5-pro",
        project_id: Optional[str] = None,
        location: str = "us-central1",
        client: Optional[Any] = None,
    ):
        self.model = model
        self.project_id = project_id
        self.location = location
        if client is not None:
            self.client = client
        else:
            try:
                from google import genai
                self.client = genai.Client(
                    project=self.project_id,
                    location=self.location,
                    vertexai=True,
                )
            except Exception:
                self.client = None

    def __call__(self, prompt: Union[str, List[Dict[str, Any]]]) -> str:
        """Execute model generation for a prompt string or chat message list."""
        if isinstance(prompt, str):
            contents: Any = prompt
        elif isinstance(prompt, list):
            parts = []
            for item in prompt:
                if isinstance(item, dict):
                    role = item.get("role", "user")
                    text = item.get("content", "")
                    parts.append(f"{role}: {text}")
                else:
                    parts.append(str(item))
            contents = "\n".join(parts)
        else:
            contents = str(prompt)

        if self.client is None:
            raise RuntimeError("Google GenAI client is not configured.")

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config={"temperature": 0.2},
        )
        return getattr(response, "text", "") or str(response or "")


FORBIDDEN_EVAL_HOSTNAMES: List[str] = [
    "GW-CORE-VPN-01",
    "SRV-PROD-PAYMENT-01",
    "DESKTOP-FIN-08",
    "SRV-DATA-01",
    "SRV-DC-01",
    "LAPTOP-CFO-01",
]

SHORT_CIRCUIT_PATTERNS: List[str] = [
    r"skip\s+(?:all\s+)?enrichment",
    r"skip\s+(?:all\s+)?investigation",
    r"skip\s+steps?\s+\d+",
    r"proceed\s+directly\s+to\s+step\s+\d+",
]

IPV4_LITERAL_REGEX: re.Pattern = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:/(?:[1-2]?\d|3[0-2]))?\b"
)

CASE_ID_REGEX: re.Pattern = re.compile(
    r"\bCASE-(?:GEN\d+-[A-Z0-9-]*?\d+|\d+)\b", re.IGNORECASE
)

MIN_FORBIDDEN_LITERAL_LENGTH = 4


def compile_forbidden_literals(literals: Optional[Sequence[str]]) -> Optional[re.Pattern]:
    """One case-insensitive alternation over the manifest literals, longest first, bounded so that
    `evil.example` does not match inside `notevil.example` and `10.10.3.4` not inside `10.10.3.45`."""
    cleaned = sorted(
        {str(x).strip() for x in (literals or []) if len(str(x).strip()) >= MIN_FORBIDDEN_LITERAL_LENGTH},
        key=lambda s: (-len(s), s),
    )
    if not cleaned:
        return None
    body = "|".join(re.escape(x) for x in cleaned)
    return re.compile(rf"(?<![A-Za-z0-9-])(?:{body})(?![A-Za-z0-9-])", re.IGNORECASE)


def load_forbidden_literals(manifest_path: Path) -> List[str]:
    """`manifest.forbidden_literals` from the Gen 5 manifest (spec section 6.5)."""
    data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    literals = data.get("forbidden_literals")
    if not isinstance(literals, list) or not literals:
        raise ValueError(f"{manifest_path} carries no forbidden_literals; rebuild with gen5_instancer.py build")
    return [str(x) for x in literals]


def is_gen5_evalset(eval_data: Dict[str, Any], eval_cases: List[Dict[str, Any]]) -> bool:
    """True when a loaded evalset is a Gen 5 bundle (top-level generation >= 5 or any case with generation >= 5)."""
    if int(eval_data.get("generation") or 0) >= 5:
        return True
    return any(int(case.get("generation") or 0) >= 5 for case in eval_cases)


def validate_runbook_candidate(
    candidate: Dict[str, str],
    forbidden_hostnames: Optional[List[str]] = None,
    seed_candidate: Optional[Dict[str, str]] = None,
    max_growth_ratio: float = 1.35,
    forbidden_literals: Optional[Sequence[str]] = None,
) -> Tuple[bool, List[str]]:
    """Validates a candidate runbook set against anti-memorization and anti-bloat guardrails.

    Rejects candidate runbooks containing:
    1. Literal IPv4 addresses or CIDR blocks (except 127.0.0.1/0.0.0.0).
    2. Hardcoded evaluation benchmark hostnames.
    3. Short-circuit / bypass directives (e.g. 'skip all enrichment').
    4. Hardcoded evaluation case identifiers (e.g. 'CASE-02', 'CASE-GEN3-01').
    5. Runbook length bloat exceeding max_growth_ratio relative to seed_candidate.
    6. Instance literals from the Gen 5 manifest forbidden_literals (memorization).

    Args:
        candidate: Mapping of runbook filenames to markdown content.
        forbidden_hostnames: Optional list of static hostnames to prohibit.
        seed_candidate: Optional seed runbooks dictionary for bloat ratio checks.
        max_growth_ratio: Maximum allowed character growth ratio vs seed (default: 1.35).
        forbidden_literals: Optional sequence of literal strings to prohibit.

    Returns:
        Tuple of (is_valid: bool, violations: List[str]).
    """
    violations: List[str] = []
    hostnames_to_check = forbidden_hostnames or FORBIDDEN_EVAL_HOSTNAMES
    literal_pattern = compile_forbidden_literals(forbidden_literals)

    for filename, content in candidate.items():
        cleaned_content = re.sub(r"\(e\.g\.[^)]*\)", "", content, flags=re.IGNORECASE)
        found_ips = IPV4_LITERAL_REGEX.findall(cleaned_content)
        for ip in found_ips:
            if ip not in ("127.0.0.1", "0.0.0.0"):
                violations.append(
                    f"{filename}: Contains hardcoded IPv4 literal '{ip}'. Runbooks must express network scopes via generic variables or telemetry query classifications."
                )

        for hostname in hostnames_to_check:
            if re.search(rf"\b{re.escape(hostname)}\b", cleaned_content, re.IGNORECASE):
                violations.append(
                    f"{filename}: Contains hardcoded evaluation benchmark hostname '{hostname}'. Runbooks must reference assets via dynamic context."
                )

        for pattern in SHORT_CIRCUIT_PATTERNS:
            match = re.search(pattern, cleaned_content, re.IGNORECASE)
            if match:
                violations.append(
                    f"{filename}: Contains short-circuit investigation directive '{match.group(0)}'. Epistemic enrichment tools must never be bypassed."
                )

        for case_match in CASE_ID_REGEX.findall(cleaned_content):
            violations.append(
                f"{filename}: Contains hardcoded evaluation case identifier '{case_match}'."
            )

        if literal_pattern is not None:
            for match in sorted({m.group(0) for m in literal_pattern.finditer(cleaned_content)}):
                violations.append(
                    f"{filename}: Contains instance literal '{match}' from the Gen 5 manifest forbidden_literals (memorization)."
                )

        if seed_candidate and filename in seed_candidate:
            seed_len = max(1, len(seed_candidate[filename]))
            ratio = len(content) / seed_len
            if ratio > max_growth_ratio:
                violations.append(
                    f"{filename}: Candidate growth ratio ({ratio:.2f}x) exceeds max_growth_ratio ({max_growth_ratio:.2f}x)."
                )

    return (len(violations) == 0, violations)


def _response_usage(response: Any) -> Dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None and hasattr(response, "get"):
        usage = response.get("usage")
    return dict(usage) if isinstance(usage, dict) else {}


class RunbookGEPAAdapter(gepa.GEPAAdapter):
    """GEPA adapter for evaluating and reflectively refining incident response runbooks."""

    def __init__(
        self,
        task_lm: str = "gemini-2.5-flash-lite",
        project_id: Optional[str] = None,
        region: str = "us-central1",
        use_live_mcp: bool = False,
        max_iterations: int = 5,
        agent_factory: Optional[Callable[..., Any]] = None,
        harness_guard: Optional[HarnessIntegrityGuard] = None,
        jev_evaluator: Optional[Any] = None,
        seed_candidate: Optional[Dict[str, str]] = None,
        max_growth_ratio: float = 1.35,
        forbidden_literals: Optional[Sequence[str]] = None,
    ):
        self.task_lm = task_lm
        resolved_project_id = (
            project_id
            or os.environ.get("PROJECT_ID")
            or os.environ.get("GCP_PROJECT_ID")
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
        )
        if not resolved_project_id:
            try:
                import google.auth
                _, default_project = google.auth.default()
                resolved_project_id = default_project
            except Exception:
                pass
        self.project_id = resolved_project_id or ""
        self.region = region
        self.use_live_mcp = use_live_mcp
        self.max_iterations = max_iterations
        self.agent_factory = agent_factory or HierarchicalSOCTier1Agent
        self.harness_guard = harness_guard
        self.jev_evaluator = jev_evaluator
        self.seed_candidate = seed_candidate
        self.max_growth_ratio = max_growth_ratio
        self.forbidden_literals = list(forbidden_literals or [])

    def evaluate(
        self,
        batch: List[Dict[str, Any]],
        candidate: Dict[str, str],
        capture_traces: bool = False,
    ) -> gepa.EvaluationBatch:
        """Evaluates runbook candidate against a batch of evaluation cases."""
        if self.harness_guard is not None:
            self.harness_guard.verify(auto_initialize=False)

        outputs: List[str] = []
        scores: List[float] = []
        trajectories: List[Dict[str, Any]] = []

        is_valid, violations = validate_runbook_candidate(
            candidate,
            seed_candidate=self.seed_candidate,
            max_growth_ratio=self.max_growth_ratio,
            forbidden_literals=self.forbidden_literals,
        )
        if not is_valid:
            rejection_msg = (
                "Candidate rejected by anti-memorization validator. Violations:\n"
                + "\n".join(f"- {v}" for v in violations)
            )
            for case in batch:
                outputs.append(rejection_msg)
                scores.append(0.0)
                trajectories.append({
                    "case_id": case.get("eval_id", ""),
                    "alert_type": case.get("name", ""),
                    "prompt": case.get("prompt", ""),
                    "cmdb_context": case.get("cmdb_context", {}),
                    "expected_verdict": case.get("ground_truth_label", ""),
                    "expected_actions": case.get("expected_actions", []),
                    "prohibited_actions": case.get("prohibited_actions", []),
                    "actual_verdict": "REJECTED_MEMORIZED",
                    "executed_actions": [],
                    "summary": rejection_msg,
                    "score": 0.0,
                    "loss_penalty": 0.0,
                    "assert_passed": False,
                    "component_name": "",
                    "trajectory": [],
                    "jev_choice": None,
                })
            return gepa.EvaluationBatch(
                outputs=outputs,
                scores=scores,
                trajectories=trajectories,
            )

        for case in batch:
            try:
                env = None
                if not self.use_live_mcp:
                    env = SocEnvironment.from_eval_case(case)

                agent = self.agent_factory(
                    runbooks_dict=candidate,
                    environment=env,
                    managed_model=self.task_lm,
                    project_id=self.project_id,
                    region=self.region,
                    use_live_mcp=self.use_live_mcp,
                )

                is_gen5 = int(case.get("generation") or 0) >= 5
                t_query = time.time()
                prompt = case.get("prompt", "")
                response = agent.query(prompt, max_iterations=self.max_iterations)
                latency_ms = int(round((time.time() - t_query) * 1000))

                resp_text = getattr(response, "response", "") or ""
                agent_traj = getattr(response, "trajectory", []) or []

                gen5_kwargs: Dict[str, Any] = {}
                if is_gen5:
                    gen5_kwargs = {
                        "prohibited_entities": case.get("prohibited_entities", []),
                        "liveness": case.get("liveness"),
                        "generation": int(case.get("generation") or 0),
                    }
                traj_verif = verify_agent_trajectory(
                    trajectory=agent_traj,
                    expected_actions=case.get("expected_actions", []),
                    prohibited_actions=case.get("prohibited_actions", []),
                    expected_entities=case.get("expected_entities", []),
                    response_text=resp_text,
                    **gen5_kwargs,
                )
                inert = bool(is_gen5 and getattr(traj_verif, "inert", False))
                entity_violations = list(getattr(traj_verif, "prohibited_entity_violations", []) or []) if is_gen5 else []

                assertions = case.get("assertions", {}) or {}
                must_contain = assertions.get("must_contain", [])
                must_not_contain = assertions.get("must_not_contain", [])
                assert_passed, _ = evaluate_assertions(
                    resp_text,
                    must_contain=must_contain,
                    must_not_contain=must_not_contain,
                )

                required_steps = max(1, int(((case.get("liveness") or {}).get("min_epistemic_steps", 1)) or 1)) if is_gen5 else 1
                epistemic_pts = 25.0 * min(1.0, traj_verif.epistemic_step_count / float(required_steps))
                if traj_verif.operator_actions_matched:
                    action_pts = 25.0
                elif traj_verif.advisor_actions_matched:
                    action_pts = 12.5
                else:
                    action_pts = 0.0

                assertion_pts = 25.0 * (1.0 if assert_passed else 0.0)
                rubric_normalized = (epistemic_pts + action_pts + assertion_pts + 25.0) / 100.0

                jev_choice: Optional[str] = None
                if self.jev_evaluator is not None:
                    rubric_text = case.get("reference", {}).get(
                        "grading_rubric", "Standard SOC Triage Rubric."
                    )
                    jev_out = self.jev_evaluator.evaluate_case(
                        prompt=prompt,
                        response=resp_text,
                        reference=case.get("reference", {}),
                        rubric=rubric_text,
                        trajectory=agent_traj,
                    )
                    rubric_normalized = (
                        0.50 * rubric_normalized
                        + 0.30 * (float(jev_out.rubric_score) / 100.0)
                        + 0.20 * float(jev_out.grounding_score)
                    )
                    jev_choice = jev_out.primary_choice

                actual_verdict = ""
                if hasattr(response, "get"):
                    actual_verdict = response.get("verdict", "")
                if not actual_verdict:
                    decision_obj = extract_soc_decision(resp_text)
                    if decision_obj is not None:
                        actual_verdict = getattr(decision_obj, "verdict", "")

                loss_penalty = calculate_loss_penalty(
                    expected_label=case.get("ground_truth_label", ""),
                    actual_verdict=actual_verdict,
                    executed_actions=traj_verif.executed_actions,
                    prohibited_actions=case.get("prohibited_actions", []),
                    prohibited_violation=bool(entity_violations) if is_gen5 else None,
                )

                op_compliance = 1.0 if traj_verif.operator_actions_matched else 0.0
                fitness = calculate_case_fitness(
                    rubric_score=rubric_normalized,
                    assertions_passed=assert_passed,
                    operator_compliance=op_compliance,
                    loss_penalty=loss_penalty,
                )
                if inert:
                    fitness = 0.0

                outputs.append(resp_text)
                scores.append(fitness)

                if capture_traces:
                    trajectories.append({
                        "case_id": case.get("eval_id", case.get("id", "")),
                        "alert_type": case.get("alert_type", getattr(response, "classification", "")),
                        "prompt": prompt,
                        "cmdb_context": case.get("cmdb_context", {}),
                        "expected_verdict": case.get("ground_truth_label", ""),
                        "expected_actions": case.get("expected_actions", []),
                        "prohibited_actions": case.get("prohibited_actions", []),
                        "actual_verdict": actual_verdict,
                        "executed_actions": traj_verif.executed_actions,
                        "summary": f"Case evaluated. Fitness: {fitness:.3f}, loss_penalty: {loss_penalty:.3f}, assert_passed: {assert_passed}",
                        "score": fitness,
                        "loss_penalty": loss_penalty,
                        "assert_passed": assert_passed,
                        "component_name": getattr(response, "runbook", ""),
                        "trajectory": agent_traj,
                        "jev_choice": jev_choice,
                        "inert": inert,
                        "prohibited_entity_violations": entity_violations,
                        "generation": int(case.get("generation") or 0),
                        "family_id": case.get("family_id"),
                        "usage": _response_usage(response),
                        "latency_ms": latency_ms,
                    })

            except Exception as e:
                import traceback
                traceback.print_exc(file=sys.stderr)
                outputs.append(f"Evaluation error: {e}")
                scores.append(0.0)
                if capture_traces:
                    trajectories.append({
                        "case_id": case.get("eval_id", case.get("id", "")),
                        "alert_type": case.get("alert_type", ""),
                        "prompt": case.get("prompt", ""),
                        "cmdb_context": case.get("cmdb_context", {}),
                        "expected_verdict": case.get("ground_truth_label", ""),
                        "expected_actions": case.get("expected_actions", []),
                        "prohibited_actions": case.get("prohibited_actions", []),
                        "actual_verdict": "ERROR",
                        "executed_actions": [],
                        "summary": f"Exception encountered during evaluation: {e}",
                        "score": 0.0,
                        "loss_penalty": 0.0,
                        "assert_passed": False,
                        "component_name": "",
                        "trajectory": [],
                        "jev_choice": None,
                    })

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
    ) -> Mapping[str, Sequence[Mapping[str, Any]]]:
        """Builds diagnostic reflection records for teacher model runbook revision."""
        dataset: Dict[str, List[Dict[str, Any]]] = {name: [] for name in components_to_update}
        trajectories = eval_batch.trajectories or []

        for comp_name in components_to_update:
            for trace in trajectories:
                trace_comp = trace.get("component_name", "")
                # If trace specifies component_name, check match; otherwise match via classification or allow all
                if trace_comp and trace_comp != comp_name:
                    continue

                score = trace.get("score", 1.0)
                loss_pen = trace.get("loss_penalty", 1.0)
                assert_pass = trace.get("assert_passed", True)

                # Filter to underperforming cases
                if score >= 0.95 and loss_pen >= 1.0 and assert_pass:
                    continue

                prompt = trace.get("prompt", "")
                executed_actions = trace.get("executed_actions", [])
                prohibited_actions = trace.get("prohibited_actions", [])
                case_id = trace.get("case_id", "")

                feedback_items: List[str] = []

                if "isolate_host" in executed_actions and "isolate_host" in prohibited_actions:
                    feedback_items.append(
                        "False positive operational disruption: The agent executed prohibited host isolation on an asset requiring safe resolution. "
                        "The runbook must guide the agent to perform epistemic verification (checking CMDB asset role, network routing classification, and corroborating SIEM events) "
                        "before taking disruptive containment actions."
                    )
                elif "MALICIOUS" in trace.get("expected_verdict", "").upper() and "isolate_host" not in executed_actions:
                    feedback_items.append(
                        "Missed containment: Confirmed active malware or C2 activity requires immediate host isolation. "
                        "The runbook must mandate host isolation for confirmed malicious threats."
                    )
                else:
                    feedback_items.append(
                        f"Triage operational failure: score={score:.2f}, loss_penalty={loss_pen:.2f}. "
                        f"Prohibited actions executed: {[a for a in executed_actions if a in prohibited_actions]}. "
                        "The runbook instructions should be clarified to avoid prohibited actions, gather verified telemetry, and adhere to operational guardrails."
                    )

                if trace.get("inert"):
                    feedback_items.append(
                        "The agent neither investigated nor decided (inert trajectory). "
                        "The runbook must require at least one enrichment lookup before any conclusion and must always end with a verdict."
                    )
                prohibited_ent_viols = trace.get("prohibited_entity_violations")
                if prohibited_ent_viols:
                    feedback_items.append(
                        f"The agent took a containment action against an entity the case marks as out of scope ({', '.join(prohibited_ent_viols)}). "
                        "The runbook must confirm the target is the alerted asset before isolating or blocking."
                    )

                jev_choice = trace.get("jev_choice")
                if jev_choice:
                    feedback_items.append(
                        f"Jev System-One Diagnostic Taxonomy: {jev_choice}."
                    )

                record = {
                    "Inputs": {
                        "case_id": case_id,
                        "alert_type": trace.get("alert_type", ""),
                        "prompt": prompt,
                        "cmdb_context": trace.get("cmdb_context", {}),
                        "expected_verdict": trace.get("expected_verdict", ""),
                        "expected_actions": trace.get("expected_actions", []),
                        "prohibited_actions": prohibited_actions,
                    },
                    "Generated Outputs": {
                        "actual_verdict": trace.get("actual_verdict", ""),
                        "executed_actions": executed_actions,
                        "summary": trace.get("summary", ""),
                    },
                    "Feedback": " ".join(feedback_items),
                }
                dataset[comp_name].append(record)

        return dataset


def build_reflection_prompt_template() -> str:
    """Build domain-specific reflection prompt template for GEPA mutation.

    Instructs the reflection LM to refine the active runbook with procedural
    epistemic verification steps, asset inventory correlation, and threat
    intelligence reputation, while strictly forbidding hardcoded network literals,
    hostnames, short-circuit bypasses, and emojis.

    Returns:
        Template string containing placeholders <curr_param> and <side_info>.
    """
    return (
        "You are an expert Security Operations Center (SOC) engineering teacher tasked with refining\n"
        "cybersecurity incident response runbooks to optimize Tier 1 autonomous agent performance.\n\n"
        "Here is the active incident response runbook component to improve:\n"
        "```markdown\n"
        "<curr_param>\n"
        "```\n\n"
        "The following diagnostic evaluation traces contain cases where the autonomous agent underperformed,\n"
        "including case context, inputs, actual actions, and concrete feedback:\n"
        "```\n"
        "<side_info>\n"
        "```\n\n"
        "Refinement Guidelines and Operational Guardrails:\n"
        "1. Epistemic Evidence Verification Sequence: Refine the runbook into a disciplined 4-stage procedural flow:\n"
        "   - Stage A: Asset Identity & CMDB Context: Query lookup_entity to determine asset business role, criticality, and authorized tags.\n"
        "   - Stage B: Network Routing & Scope Verification: Query get_ip_address_report or get_domain_report to determine if target infrastructure is public, private, or reserved documentation space.\n"
        "   - Stage C: Threat Intelligence Reputation: Check GTI reputation scores and known malware associations.\n"
        "   - Stage D: Corroboration of Malicious Activity: Correlate telemetry with observed behaviors (e.g. active malware, C2 beaconing vs benign scanning).\n"
        "2. Mandatory Epistemic Investigation (No Short-Circuits): Forbid instructions that tell the analyst to 'skip all enrichment' or 'bypass investigation'. The analyst must always execute telemetry queries to substantiate their findings.\n"
        "3. Anti-Memorization Rule (Generalization): Strictly DO NOT hardcode specific IP addresses, CIDR blocks, domain names, or hostnames in the runbook. All triage logic must rely on dynamic variables (e.g. ${IOC_VALUE}, ${ASSET_ROLE}, ${IP_ROUTING_TYPE}).\n"
        "4. Strict Malicious Containment: Maintain unambiguous containment protocols (isolate_host, block_indicator) when high-severity malicious activity is corroborated.\n"
        "5. Output Standards: Output exclusively the refined markdown runbook without conversational preamble.\n"
        "6. Strictly NO EMOJIS: Do not include any emojis anywhere in the runbook content or markdown headings.\n\n"
        "Provide the complete revised runbook inside ```markdown blocks."
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """Build command-line argument parser for GEPA runbook optimization.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        description="Evolve SOC incident response runbooks using GEPA Pareto optimization."
    )
    parser.add_argument(
        "--max-metric-calls",
        type=int,
        default=15,
        help="Maximum metric evaluation calls (default: 15).",
    )
    parser.add_argument(
        "--task-lm",
        type=str,
        default="gemini-2.5-flash-lite",
        help="Task model flavor or name for agent triage (default: gemini-2.5-flash-lite).",
    )
    parser.add_argument(
        "--reflection-lm",
        type=str,
        default="gemini-2.5-pro",
        help="Teacher model for reflective mutation (default: gemini-2.5-pro).",
    )
    project_default = (
        os.environ.get("PROJECT_ID")
        or os.environ.get("GCP_PROJECT_ID")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
    )
    if not project_default:
        try:
            import google.auth
            _, default_project = google.auth.default()
            project_default = default_project
        except Exception:
            pass
    project_default = project_default or ""
    region_default = os.environ.get("REGION", "us-central1")
    parser.add_argument(
        "--project-id",
        type=str,
        default=project_default,
        help=f"Google Cloud Project ID (default: {project_default}).",
    )
    parser.add_argument(
        "--region",
        type=str,
        default=region_default,
        help=f"Google Cloud Region (default: {region_default}).",
    )
    parser.add_argument(
        "--evalset",
        type=str,
        default=None,
        help="Explicit evalset JSON (legacy; Gen 5 bundles are refused on this path).",
    )
    parser.add_argument(
        "--train-split",
        choices=list(gen5_exposure.SPLITS),
        default="train",
        help="Gen 5 split for reflection minibatches",
    )
    parser.add_argument(
        "--val-split",
        choices=list(gen5_exposure.SPLITS),
        default="validation",
        help="Gen 5 split for Pareto selection, the noise floor, and the staircase",
    )
    parser.add_argument(
        "--purpose",
        default="gepa runbook hillclimb",
        help="Purpose recorded in the exposure ledger",
    )
    parser.add_argument(
        "--manifest",
        default=str(gen5_exposure.MANIFEST_PATH),
        help="Gen 5 manifest providing forbidden_literals",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run id shared by the ledger entries and evolution_metadata.json (default: generated)",
    )
    parser.add_argument(
        "--noise-only",
        action="store_true",
        default=False,
        help="Measure the K-run seed noise floor on --val-split, write noise_floor.json, and exit",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="configs/runbooks/gepa_evolved",
        help="Output directory for evolved runbooks (default: configs/runbooks/gepa_evolved).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for optimization reproducibility (default: 42).",
    )
    parser.add_argument(
        "--split-train-val",
        action="store_true",
        default=False,
        help="Split dataset into separate train and validation subsets (default: False, optimizes on full dataset).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Execute single evaluation batch on sample cases without mutation.",
    )
    parser.add_argument(
        "--lock-file",
        type=str,
        default=None,
        help="Path to SHA-256 evaluation harness lockfile (default: .eval_harness_lock.json).",
    )
    parser.add_argument(
        "--approve-harness",
        action="store_true",
        default=False,
        help="Approve current evaluation harness state and update lockfile.",
    )
    parser.add_argument(
        "--noise-runs",
        type=int,
        default=2,
        help="K >= 2 seed passes on the validation split for the noise floor (0 disables)",
    )
    parser.add_argument(
        "--min-delta",
        type=float,
        default=0.015,
        help="Minimum required validation score improvement over baseline (default: 0.015).",
    )
    parser.add_argument(
        "--max-growth-ratio",
        type=float,
        default=1.35,
        help="Maximum allowed runbook length growth ratio relative to seed (default: 1.35).",
    )
    parser.add_argument(
        "--judge-backend",
        choices=["jev", "deterministic", "mock"],
        default="deterministic",
        help="Inner-loop judge backend: 'jev', 'deterministic', or 'mock' (default: deterministic).",
    )
    parser.add_argument(
        "--cost-staircase",
        action="store_true",
        default=False,
        help="Run post-convergence model cost staircase walk to identify cheapest safe model tier.",
    )
    parser.add_argument(
        "--cost-tolerance",
        type=float,
        default=0.05,
        help="Maximum acceptable fitness drop from ceiling model during cost staircase walk (default: 0.05).",
    )
    return parser


def main(args: Optional[List[str]] = None) -> int:
    """CLI entrypoint for GEPA runbook optimization.

    Args:
        args: Optional list of CLI arguments (uses sys.argv[1:] if None).

    Returns:
        0 on success, non-zero on failure.
    """
    parser = build_arg_parser()
    parsed_args = parser.parse_args(args)

    print(f"Loading seed runbooks from {DEFAULT_RUNBOOKS_DIR}...")
    seed_candidate = load_seed_runbooks()

    run_id = parsed_args.run_id or gen5_exposure.new_run_id()
    exposure_entries: List[Dict[str, Any]] = []
    forbidden_literals: List[str] = []
    manifest_path = Path(parsed_args.manifest) if Path(parsed_args.manifest).is_absolute() else ROOT_DIR / parsed_args.manifest

    if parsed_args.evalset:
        evalset_path = ROOT_DIR / parsed_args.evalset if not Path(parsed_args.evalset).is_absolute() else Path(parsed_args.evalset)
        if not evalset_path.exists():
            print(f"Evaluation dataset not found: {evalset_path}", file=sys.stderr)
            return 1

        eval_data = json.loads(evalset_path.read_text(encoding="utf-8"))
        eval_cases = eval_data.get("eval_cases", [])
        if not eval_cases:
            print(f"No evaluation cases found in: {evalset_path}", file=sys.stderr)
            return 1

        if is_gen5_evalset(eval_data, eval_cases):
            print(
                f"{evalset_path} is a Gen 5 bundle; --evalset bypasses the exposure ledger and the final_test seal. "
                "Drop --evalset and use --train-split/--val-split (default: train/validation) so every load goes "
                "through gen5_exposure.load_split.",
                file=sys.stderr,
            )
            return 1

        if parsed_args.split_train_val:
            if len(eval_cases) <= 6:
                print(
                    "--split-train-val requires at least 7 evaluation cases: "
                    "6 for training and at least 1 for validation. Add validation cases "
                    "before running with this flag.",
                    file=sys.stderr,
                )
                return 1
            trainset = eval_cases[:6]
            valset = eval_cases[6:]
        else:
            trainset = eval_cases
            valset = eval_cases
        if manifest_path.exists():
            forbidden_literals = load_forbidden_literals(manifest_path)
        train_split_name, val_split_name = ("legacy[:6]", "legacy[6:]") if parsed_args.split_train_val else ("legacy", "legacy")
    else:
        if parsed_args.train_split == parsed_args.val_split:
            print("--train-split and --val-split must differ.", file=sys.stderr)
            return 1
        try:
            trainset, train_entry = gen5_exposure.load_split(
                parsed_args.train_split, purpose=f"{parsed_args.purpose} (train)", model=parsed_args.task_lm, run_id=run_id
            )
            valset, val_entry = gen5_exposure.load_split(
                parsed_args.val_split, purpose=f"{parsed_args.purpose} (validation)", model=parsed_args.task_lm, run_id=run_id
            )
        except (gen5_exposure.FinalTestSealedError, gen5_exposure.ExposureError) as err:
            print(f"Gen 5 split load refused: {err}", file=sys.stderr)
            return 1
        exposure_entries = [train_entry, val_entry]
        eval_cases = valset
        evalset_path = gen5_exposure.bundle_path(parsed_args.val_split)
        forbidden_literals = load_forbidden_literals(manifest_path)
        train_split_name, val_split_name = parsed_args.train_split, parsed_args.val_split

    output_dir = ROOT_DIR / parsed_args.output_dir if not Path(parsed_args.output_dir).is_absolute() else Path(parsed_args.output_dir)

    if parsed_args.lock_file:
        lock_file_path = (
            Path(parsed_args.lock_file)
            if Path(parsed_args.lock_file).is_absolute()
            else (ROOT_DIR / parsed_args.lock_file)
        )
        protected_paths: Sequence[Path | str] = (
            DEFAULT_PROTECTED_HARNESS_PATHS
            if evalset_path.resolve().is_relative_to(ROOT_DIR.resolve())
            else [evalset_path]
        )
        guard_root = ROOT_DIR if evalset_path.resolve().is_relative_to(ROOT_DIR.resolve()) else evalset_path.parent
    elif evalset_path.resolve().is_relative_to(ROOT_DIR.resolve()):
        lock_file_path = ROOT_DIR / ".eval_harness_lock.json"
        protected_paths = DEFAULT_PROTECTED_HARNESS_PATHS
        guard_root = ROOT_DIR
    else:
        lock_file_path = evalset_path.parent / ".eval_harness_lock.json"
        protected_paths = [evalset_path]
        guard_root = evalset_path.parent

    harness_guard = HarnessIntegrityGuard(
        root_dir=guard_root,
        lock_file=lock_file_path,
        protected_paths=protected_paths,
    )
    if parsed_args.approve_harness or not evalset_path.resolve().is_relative_to(ROOT_DIR.resolve()):
        harness_guard.approve_and_save()
    else:
        harness_guard.verify(auto_initialize=True)

    jev_evaluator: Optional[JevSocJudgeEvaluator] = None
    if parsed_args.judge_backend == "jev":
        jev_evaluator = JevSocJudgeEvaluator(
            backend=GeminiSystem1Backend(
                project_id=parsed_args.project_id,
                location=parsed_args.region,
            )
        )
    elif parsed_args.judge_backend == "mock":
        jev_evaluator = JevSocJudgeEvaluator(backend=MockJevBackend())

    adapter = RunbookGEPAAdapter(
        task_lm=parsed_args.task_lm,
        project_id=parsed_args.project_id,
        region=parsed_args.region,
        agent_factory=HierarchicalSOCTier1Agent,
        harness_guard=harness_guard,
        jev_evaluator=jev_evaluator,
        seed_candidate=seed_candidate,
        max_growth_ratio=parsed_args.max_growth_ratio,
        forbidden_literals=forbidden_literals,
    )

    if parsed_args.dry_run:
        print("Dry run mode enabled: executing single evaluation batch on 2 cases...")
        dry_batch = eval_cases[:2]
        eval_batch = adapter.evaluate(dry_batch, seed_candidate, capture_traces=True)
        print(f"Dry run complete. Evaluated {len(eval_batch.scores)} cases.")
        for i, score in enumerate(eval_batch.scores):
            print(f"  Case {i + 1} score: {score:.3f}")
        return 0

    tau_accept = float(parsed_args.min_delta)
    noise_metrics_dict: Optional[Dict[str, Any]] = None
    if parsed_args.noise_runs >= 2:
        runs: List[List[float]] = []
        for _ in range(int(parsed_args.noise_runs)):
            batch = adapter.evaluate(valset, seed_candidate, capture_traces=False)
            scores_k = getattr(batch, "scores", None)
            if (
                not isinstance(scores_k, list) or not scores_k
                or not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in scores_k)
            ):
                runs = []
                break
            runs.append([float(x) for x in scores_k])
        if runs and len({len(r) for r in runs}) == 1:
            nf = estimate_noise_floor(
                *runs, min_delta=parsed_args.min_delta, case_ids=[str(c.get("eval_id", i)) for i, c in enumerate(valset)]
            )
            tau_accept = nf.tau_accept
            noise_metrics_dict = nf.to_dict()
            write_noise_floor_json(
                nf,
                output_dir / "noise_floor.json",
                extra={
                    "model": parsed_args.task_lm,
                    "split": val_split_name,
                    "run_id": run_id,
                    "git_sha": gen5_exposure.git_sha(),
                    "gate_mean_spread_max": 0.02,
                    "gate_passed": nf.aggregate_noise <= 0.02,
                },
            )
            print(
                f"Noise floor over {nf.runs} runs: mean spread {nf.aggregate_noise:.4f}, "
                f"mean per-case std {nf.mean_case_std:.4f}, tau_accept {nf.tau_accept:.4f} "
                f"(gate: spread <= 0.02 {'PASS' if nf.aggregate_noise <= 0.02 else 'FAIL'})"
            )
        else:
            print("Noise floor skipped: the adapter did not return numeric score lists.", file=sys.stderr)

    if parsed_args.noise_only:
        if noise_metrics_dict is None:
            print("--noise-only requires --noise-runs >= 2 and numeric scores.", file=sys.stderr)
            return 1
        metadata_only = {"run_id": run_id, "task_lm": parsed_args.task_lm, "train_split": train_split_name,
                         "val_split": val_split_name, "exposure": exposure_entries, "noise_floor": noise_metrics_dict,
                         "noise_only": True, "runbooks_written": False}
        write_evolution_metadata(output_dir, metadata_only)
        return 0

    reflection_lm = GoogleGenAILM(
        model=parsed_args.reflection_lm,
        project_id=parsed_args.project_id,
        location=parsed_args.region,
    )

    reflection_prompt_template = build_reflection_prompt_template()

    print(f"Starting GEPA optimization (max_metric_calls={parsed_args.max_metric_calls}, seed={parsed_args.seed})...")
    result = gepa.optimize(
        seed_candidate=seed_candidate,
        trainset=trainset,
        valset=valset,
        adapter=adapter,
        reflection_lm=reflection_lm,
        max_metric_calls=parsed_args.max_metric_calls,
        reflection_prompt_template=reflection_prompt_template,
        candidate_selection_strategy="pareto",
        seed=parsed_args.seed,
    )

    # GEPA scores align with candidate indices; best_idx can refer to a candidate
    # rejected by our anti-memorization validation. Rank only valid candidates.
    candidates = result.candidates
    scores = result.val_aggregate_scores
    if len(candidates) != len(scores):
        print("GEPA returned mismatched candidate and validation score counts.", file=sys.stderr)
        return 1

    for index, score in enumerate(scores):
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
            print(f"GEPA returned an invalid validation score for candidate {index}.", file=sys.stderr)
            return 1

    ledger = HillclimbLedger(output_dir / "hillclimb_ledger.jsonl")
    composite_sha = harness_guard.compute_composite_sha256()
    val_subscores = getattr(result, "val_subscores", None) or []
    baseline_subscores = (
        val_subscores[0]
        if (len(val_subscores) > 0 and isinstance(val_subscores[0], dict) and val_subscores[0])
        else None
    )

    valid_count = 0
    selected_index: Optional[int] = None
    selected_score: Optional[float] = None
    for index, (candidate, score) in enumerate(zip(candidates, scores)):
        if not isinstance(candidate, dict) or not candidate or not all(
            isinstance(name, str) and isinstance(text, str)
            for name, text in candidate.items()
        ):
            continue
        is_valid, violations = validate_runbook_candidate(
            candidate,
            seed_candidate=seed_candidate,
            max_growth_ratio=parsed_args.max_growth_ratio,
            forbidden_literals=forbidden_literals,
        )
        if not is_valid:
            ledger.append_entry(
                iteration=index,
                harness_sha256=composite_sha,
                train_score=None,
                val_score=float(score),
                tau_accept=tau_accept,
                decision="REJECTED_INVALID",
                rationale="; ".join(violations),
                metadata={"task_lm": parsed_args.task_lm},
            )
            continue

        valid_count += 1

        cand_subscores = (
            val_subscores[index]
            if (index < len(val_subscores) and isinstance(val_subscores[index], dict) and val_subscores[index])
            else None
        )
        if index > 0 and baseline_subscores is not None and cand_subscores is not None:
            acc = evaluate_candidate_acceptance(
                baseline_scores=baseline_subscores,
                candidate_scores=cand_subscores,
                tau_accept=tau_accept,
            )
            ledger.append_entry(
                iteration=index,
                harness_sha256=composite_sha,
                train_score=None,
                val_score=float(score),
                tau_accept=tau_accept,
                decision=acc.status,
                rationale=acc.reason,
                metadata={"task_lm": parsed_args.task_lm, "regressed_cases": acc.regressed_cases},
            )
            if acc.accepted and (selected_score is None or score > selected_score):
                selected_index = index
                selected_score = float(score)
        else:
            # Strict comparison preserves the earliest candidate when scores tie.
            is_better = selected_score is None or score > selected_score
            ledger.append_entry(
                iteration=index,
                harness_sha256=composite_sha,
                train_score=None,
                val_score=float(score),
                tau_accept=tau_accept,
                decision="KEPT" if is_better else "SKIPPED_LOWER_SCORE",
                rationale="Baseline or aggregate validation score comparison",
                metadata={"task_lm": parsed_args.task_lm},
            )
            if is_better:
                selected_index = index
                selected_score = float(score)

    reason, write_runbooks = select_candidate_outcome(selected_index, valid_count)
    best_candidate = seed_candidate if selected_index in (None, 0) else candidates[selected_index]
    metadata: Dict[str, Any] = {
        "run_id": run_id,
        "task_lm": parsed_args.task_lm,
        "reflection_lm": parsed_args.reflection_lm,
        "max_metric_calls": parsed_args.max_metric_calls,
        "seed": parsed_args.seed,
        "evalset": str(evalset_path) if parsed_args.evalset else None,
        "train_split": train_split_name,
        "val_split": val_split_name,
        "exposure": exposure_entries,
        "forbidden_literals_count": len(forbidden_literals),
        "selected_candidate_index": selected_index,
        "selected_validation_score": selected_score,
        "best_score": selected_score,
        "selection_reason": reason,
        "runbooks_written": write_runbooks,
        "harness_composite_sha256": composite_sha,
        "tau_accept": tau_accept,
    }
    if noise_metrics_dict is not None:
        metadata["noise_floor"] = noise_metrics_dict

    if parsed_args.cost_staircase:
        def _staircase_eval(
            tier: str, cand: Dict[str, str], cases: List[Dict[str, Any]]
        ) -> Tuple[List[float], List[float], Dict[str, Any]]:
            tier_adapter = RunbookGEPAAdapter(
                task_lm=tier,
                project_id=parsed_args.project_id,
                region=parsed_args.region,
                agent_factory=HierarchicalSOCTier1Agent,
                harness_guard=harness_guard,
                jev_evaluator=jev_evaluator,
                seed_candidate=seed_candidate,
                max_growth_ratio=parsed_args.max_growth_ratio,
                forbidden_literals=forbidden_literals,
            )
            batch_res = tier_adapter.evaluate(cases, cand, capture_traces=True)
            sc_list = [float(x) for x in (batch_res.scores or [])]
            lp_list = [
                float(t.get("loss_penalty", 1.0))
                for t in (batch_res.trajectories or [])
            ]
            if not lp_list and sc_list:
                lp_list = [1.0 for _ in sc_list]
            traces = list(batch_res.trajectories or [])
            telemetry = {
                "inert": [bool(t.get("inert", False)) for t in traces],
                "tokens_in": [(t.get("usage") or {}).get("prompt_tokens") for t in traces],
                "tokens_out": [(t.get("usage") or {}).get("completion_tokens") for t in traces],
                "latency_ms": [t.get("latency_ms") for t in traces],
            }
            return sc_list, lp_list, telemetry

        staircase_report = run_cost_staircase_walk(
            candidate=best_candidate,
            eval_cases=valset,
            evaluator_fn=_staircase_eval,
            model_tiers=DEFAULT_COST_STAIRCASE_TIERS,
            tolerance=parsed_args.cost_tolerance,
        )
        staircase_path = output_dir / "cost_staircase_report.json"
        staircase_path.parent.mkdir(parents=True, exist_ok=True)
        staircase_path.write_text(
            json.dumps(staircase_report.to_dict(), indent=2),
            encoding="utf-8",
        )
        metadata["cost_staircase"] = staircase_report.to_dict()

    if write_runbooks:
        print(f"Saving evolved runbooks to {output_dir}...")
        save_runbooks(candidate=best_candidate, output_dir=output_dir, metadata=metadata)
    else:
        print(f"Seed retained ({reason}); runbooks in {output_dir} are left untouched.")
        write_evolution_metadata(output_dir, metadata)
    print("Runbook evolution complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
