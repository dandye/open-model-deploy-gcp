"""SOC Evaluation State Serializer and Jev System One Judge Evaluator."""

import json
from typing import Any, Dict, List, Optional
from agent.jev_judge import BaseJevBackend, JevEvaluationOutput

# Standard SOC Failure Mode Taxonomy for Jev Choice primitive
SOC_FAILURE_TAXONOMY: Dict[str, str] = {
    "A": "FLAWLESS_CONTAINMENT",
    "B": "UNGROUNDED_HALLUCINATED_CLAIM",
    "C": "MISSED_MALICIOUS_BREACH",
    "D": "OVER_CONTAINMENT_FALSE_ALARM",
    "E": "PREMATURE_TERMINATION_ZERO_TOOLS",
    "F": "RUNBOOK_PROCEDURAL_VIOLATION",
    "G": "DEGRADED_MODE_FAILURE",
}


def build_soc_evaluation_state(
    prompt: str,
    response: str,
    reference: Dict[str, Any],
    rubric: str,
    trajectory: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Serializes alert, trajectory, response, reference, and rubric into Jev state."""
    if trajectory and len(trajectory) > 0:
        traj_lines = []
        for step in trajectory:
            t_num = step.get("iteration", step.get("step", "?"))
            t_name = step.get("tool", "unknown")
            t_in = json.dumps(step.get("args", step.get("input", {})))
            t_obs = str(step.get("observation", ""))[:500]
            traj_lines.append(
                f"Step {t_num}: Tool '{t_name}' invoked with {t_in} -> Observation: {t_obs}"
            )
        traj_str = "\n".join(traj_lines)
    else:
        traj_str = (
            "NO TOOLS WERE INVOKED DURING THIS INVESTIGATION (0 tool calls executed)."
        )

    return f"""### Incident Alert Prompt:
{prompt.strip()}

### Actual Tool Execution Trajectory:
{traj_str}

### Agent Response:
{response.strip()}

### Ground Truth Reference:
{json.dumps(reference, indent=2)}

### Operational Grading Rubric:
{rubric.strip()}
"""


class JevSocJudgeEvaluator:
    """Evaluates SOC triage episodes using Jev decision primitives."""

    def __init__(self, backend: BaseJevBackend):
        self.backend = backend

    def evaluate_case(
        self,
        prompt: str,
        response: str,
        reference: Dict[str, Any],
        rubric: str,
        trajectory: Optional[List[Dict[str, Any]]] = None,
    ) -> JevEvaluationOutput:
        """Executes Score, Noul, and Choice primitives across serialized state."""
        state = build_soc_evaluation_state(
            prompt=prompt,
            response=response,
            reference=reference,
            rubric=rubric,
            trajectory=trajectory,
        )

        # 1. Score Primitive (Continuous 0-100 rubric expected score)
        score_res = self.backend.evaluate_score(state, num_levels=10)

        # 2. Noul Primitives (Calibrated Grounding and Operational Pass probabilities)
        noul_ground = self.backend.evaluate_noul(
            state,
            question="Are all claims, IOC classifications, and forensic assertions in the agent response strictly grounded and corroborated by the actual tool execution trajectory without hallucination?",
        )
        noul_pass = self.backend.evaluate_noul(
            state,
            question="Did the agent satisfy mandatory SOC triage and containment standards for this incident without fatal operational errors?",
        )

        # 3. Choice Primitive (Diagnostic Taxonomy)
        choice_res = self.backend.evaluate_choice(
            state,
            question="Which category best describes the agent's primary operational performance or failure mode?",
            options=SOC_FAILURE_TAXONOMY,
        )

        critique = (
            f"[Jev System-One Decision] Diagnosis: {choice_res.selected} | "
            f"Pass Probability: {noul_pass.probability:.1%} | "
            f"Grounding Probability: {noul_ground.probability:.1%} | "
            f"Rubric Expected Score: {score_res.expected_score:.1f}/100"
        )

        return JevEvaluationOutput(
            rubric_score=score_res.expected_score,
            passed=noul_pass.verdict and score_res.expected_score >= 70.0,
            grounding_score=round(noul_ground.probability, 3),
            primary_choice=choice_res.selected,
            critique=critique,
            raw_metadata={
                "score_levels": score_res.level_probs,
                "noul_pass_prob": noul_pass.probability,
                "noul_grounding_prob": noul_ground.probability,
                "choice_probs": choice_res.candidate_probs,
            },
        )

    @staticmethod
    def to_semantic_judge_result(output: JevEvaluationOutput) -> Dict[str, Any]:
        """Converts JevEvaluationOutput into a dictionary compatible with SemanticJudgeResult."""
        return {
            "rubric_score": output.rubric_score,
            "passed": output.passed,
            "grounding_score": output.grounding_score,
            "critique": output.critique,
        }
