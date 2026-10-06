"""Unit tests for the GLiNER2.5-Decide Jev backend (fake engine, no torch)."""

import sys
from typing import Any, Dict, List, Optional

import pytest

from agent.jev_evaluator import SOC_FAILURE_TAXONOMY, build_soc_evaluation_state
from agent import jev_backend_gliner as gl
from agent.jev_backend_gliner import GlinerDecideBackend, GlinerDecideEngine, fit_state_to_budget
from agent.jev_judge import BaseJevBackend

ORACLE_HEADS: Dict[str, Dict[str, float]] = {
    gl.SCORE_HEAD: {str(i): 0.0 for i in range(11)} | {"8": 0.6, "9": 0.4},
    gl.GROUNDED_HEAD: {"yes": 0.27, "no": 0.73},
    gl.PASS_HEAD: {"yes": 0.41, "no": 0.59},
    gl.FAILURE_MODE_HEAD: {
        "FLAWLESS_CONTAINMENT": 0.78,
        "UNGROUNDED_HALLUCINATED_CLAIM": 0.02,
        "MISSED_MALICIOUS_BREACH": 0.05,
        "OVER_CONTAINMENT_FALSE_ALARM": 0.05,
        "PREMATURE_TERMINATION_ZERO_TOOLS": 0.04,
        "RUNBOOK_PROCEDURAL_VIOLATION": 0.03,
        "DEGRADED_MODE_FAILURE": 0.03,
    },
}

GROUNDING_QUESTION = (
    "Are all claims, IOC classifications, and forensic assertions in the agent response "
    "strictly grounded and corroborated by the actual tool execution trajectory without hallucination?"
)
PASS_QUESTION = (
    "Did the agent satisfy mandatory SOC triage and containment standards for this incident "
    "without fatal operational errors?"
)
CHOICE_QUESTION = "Which category best describes the agent's primary operational performance or failure mode?"


class FakeEngine:
    """Stands in for the model: records every text it classifies and counts words as tokens."""

    def __init__(self, heads: Optional[Dict[str, Dict[str, float]]] = None):
        self.heads = heads or ORACLE_HEADS
        self.calls: List[str] = []

    def classify_heads(self, text: str) -> Dict[str, Dict[str, float]]:
        self.calls.append(text)
        return {head: dict(probs) for head, probs in self.heads.items()}

    def count_tokens(self, text: str) -> int:
        return len(text.split())


def make_state(n_steps: int = 3, obs_words: int = 5) -> str:
    trajectory = [
        {"iteration": i + 1, "tool": f"tool_{i + 1}", "args": {"q": i}, "observation": " ".join([f"obs{i}"] * obs_words)}
        for i in range(n_steps)
    ]
    return build_soc_evaluation_state(
        prompt="Alert: suspicious login from 203.0.113.9",
        response="Verdict: malicious. Isolated host WS-01.",
        reference={"verdict": "MALICIOUS", "required_action": "isolate"},
        rubric="Full credit for isolating WS-01 after confirming the indicator.",
        trajectory=trajectory,
    )


def test_backend_is_a_jev_backend_with_pinned_defaults():
    backend = GlinerDecideBackend(engine=FakeEngine())
    assert isinstance(backend, BaseJevBackend)
    assert backend.model_id == "fastino/GLiNER2.5-Decide"
    assert backend.revision == "7ee5da4c2415e32259bcdc0b1a7367c32ce8d6f6"
    assert backend.threads == 8
    assert backend.token_budget == 2048


def test_evaluate_score_is_the_expected_value_of_the_ordinal_head():
    backend = GlinerDecideBackend(engine=FakeEngine())
    res = backend.evaluate_score(make_state(), num_levels=10)
    assert res.expected_score == pytest.approx(84.0)
    assert res.raw_level == 8
    assert res.level_probs[8] == pytest.approx(0.6)
    assert res.level_probs[9] == pytest.approx(0.4)
    assert set(res.level_probs) == set(range(11))


def test_evaluate_score_rejects_other_level_counts():
    backend = GlinerDecideBackend(engine=FakeEngine())
    with pytest.raises(ValueError, match="num_levels"):
        backend.evaluate_score(make_state(), num_levels=5)


def test_pass_gate_is_the_flawless_mass_of_the_taxonomy_head():
    backend = GlinerDecideBackend(engine=FakeEngine())
    res = backend.evaluate_noul(make_state(), PASS_QUESTION)
    assert res.probability == pytest.approx(0.78)
    assert res.verdict is True
    assert res.details["source_head"] == gl.FAILURE_MODE_HEAD
    assert res.details["formula"] == "P(FLAWLESS_CONTAINMENT)"
    assert res.details["raw_head_p_yes"] == pytest.approx(0.41)


def test_grounding_gate_is_one_minus_the_ungrounded_mass():
    backend = GlinerDecideBackend(engine=FakeEngine())
    res = backend.evaluate_noul(make_state(), GROUNDING_QUESTION)
    assert res.probability == pytest.approx(0.98)
    assert res.verdict is True
    assert res.details["formula"] == "1 - P(UNGROUNDED_HALLUCINATED_CLAIM)"
    assert res.details["raw_head_p_yes"] == pytest.approx(0.27)


def test_gate_verdicts_use_the_configured_thresholds():
    heads = {**ORACLE_HEADS, gl.FAILURE_MODE_HEAD: {**ORACLE_HEADS[gl.FAILURE_MODE_HEAD]}}
    heads[gl.FAILURE_MODE_HEAD].update({"FLAWLESS_CONTAINMENT": 0.44, "UNGROUNDED_HALLUCINATED_CLAIM": 0.35})
    backend = GlinerDecideBackend(engine=FakeEngine(heads))
    assert backend.evaluate_noul(make_state(), PASS_QUESTION).verdict is False
    assert backend.evaluate_noul(make_state(), GROUNDING_QUESTION).verdict is False
    lenient = GlinerDecideBackend(engine=FakeEngine(heads), pass_threshold=0.40, grounding_threshold=0.60)
    assert lenient.evaluate_noul(make_state(), PASS_QUESTION).verdict is True
    assert lenient.evaluate_noul(make_state(), GROUNDING_QUESTION).verdict is True


def test_evaluate_choice_maps_taxonomy_options_to_head_labels():
    backend = GlinerDecideBackend(engine=FakeEngine())
    res = backend.evaluate_choice(make_state(), CHOICE_QUESTION, SOC_FAILURE_TAXONOMY)
    assert res.selected == "FLAWLESS_CONTAINMENT"
    assert set(res.candidate_probs) == set(SOC_FAILURE_TAXONOMY.values())
    assert res.candidate_probs["FLAWLESS_CONTAINMENT"] == pytest.approx(0.78)
    assert sum(res.candidate_probs.values()) == pytest.approx(1.0)


def test_evaluate_choice_rejects_options_outside_the_taxonomy():
    backend = GlinerDecideBackend(engine=FakeEngine())
    with pytest.raises(ValueError, match="taxonomy"):
        backend.evaluate_choice(make_state(), CHOICE_QUESTION, {"A": "GOOD", "B": "BAD"})


def test_one_model_call_serves_score_noul_and_choice_for_the_same_state():
    engine = FakeEngine()
    backend = GlinerDecideBackend(engine=engine)
    state = make_state()
    backend.evaluate_score(state)
    backend.evaluate_noul(state, GROUNDING_QUESTION)
    backend.evaluate_noul(state, PASS_QUESTION)
    backend.evaluate_choice(state, CHOICE_QUESTION, SOC_FAILURE_TAXONOMY)
    assert len(engine.calls) == 1
    backend.evaluate_score(make_state(n_steps=4))
    assert len(engine.calls) == 2


def test_cache_is_bounded_and_keyed_by_state_content():
    engine = FakeEngine()
    backend = GlinerDecideBackend(engine=engine, cache_size=2)
    states = [make_state(n_steps=n) for n in (1, 2, 3)]
    for state in states:
        backend.evaluate_score(state)
    assert len(engine.calls) == 3
    backend.evaluate_score(states[2])
    assert len(engine.calls) == 3
    backend.evaluate_score(states[0])
    assert len(engine.calls) == 4


def test_fit_state_keeps_a_state_within_budget_untouched():
    state = make_state(n_steps=3)
    fitted, info = fit_state_to_budget(state, lambda t: len(t.split()), token_budget=10_000)
    assert fitted == state
    assert info["steps_omitted"] == 0
    assert info["within_budget"] is True
    assert info["tokens_before"] == info["tokens_after"] == len(state.split())


def test_fit_state_drops_middle_trajectory_steps_and_keeps_the_rubric():
    state = make_state(n_steps=12, obs_words=40)
    count = lambda t: len(t.split())
    budget = count(state) - 120
    fitted, info = fit_state_to_budget(state, count, token_budget=budget)
    assert info["within_budget"] is True
    assert info["tokens_after"] <= budget
    assert 0 < info["steps_omitted"] < 12
    assert "Step 1: Tool 'tool_1'" in fitted
    assert "Step 12: Tool 'tool_12'" in fitted
    assert f"{info['steps_omitted']} trajectory steps omitted" in fitted
    assert "### Operational Grading Rubric:" in fitted
    assert "Full credit for isolating WS-01" in fitted
    assert fitted.index("Step 1: Tool 'tool_1'") < fitted.index("steps omitted") < fitted.index("Step 12: Tool 'tool_12'")


def test_fit_state_reports_when_the_budget_cannot_be_met():
    state = make_state(n_steps=4, obs_words=10)
    fitted, info = fit_state_to_budget(state, lambda t: len(t.split()), token_budget=20)
    assert info["within_budget"] is False
    assert info["steps_omitted"] == 2
    assert "### Operational Grading Rubric:" in fitted


def test_fit_state_leaves_tool_less_states_alone():
    state = build_soc_evaluation_state("p", "r", {"verdict": "BENIGN"}, "rubric", trajectory=None)
    fitted, info = fit_state_to_budget(state, lambda t: len(t.split()), token_budget=5)
    assert fitted == state
    assert info["steps_omitted"] == 0
    assert info["within_budget"] is False


def test_backend_sends_the_trimmed_state_to_the_model_and_counts_it():
    engine = FakeEngine()
    state = make_state(n_steps=12, obs_words=40)
    backend = GlinerDecideBackend(engine=engine, token_budget=len(state.split()) - 120)
    backend.evaluate_score(state)
    assert len(engine.calls) == 1
    assert "trajectory steps omitted" in engine.calls[0]
    assert len(engine.calls[0].split()) <= backend.token_budget
    assert backend.fit_stats == {"states_judged": 1, "states_trimmed": 1, "states_over_budget": 0}


def test_describe_reports_the_pinned_model_and_gate_derivations():
    info = GlinerDecideBackend(engine=FakeEngine()).describe()
    assert info["backend"] == "gliner_decide"
    assert info["model_id"] == "fastino/GLiNER2.5-Decide"
    assert info["revision"] == "7ee5da4c2415e32259bcdc0b1a7367c32ce8d6f6"
    assert info["token_budget"] == 2048
    assert info["threads"] == 8
    assert info["gates"]["pass"] == "P(FLAWLESS_CONTAINMENT)"
    assert info["gates"]["grounding"] == "1 - P(UNGROUNDED_HALLUCINATED_CLAIM)"
    assert info["pass_threshold"] == 0.5
    assert info["grounding_threshold"] == 0.70


def test_backend_construction_does_not_import_torch_or_gliner2():
    before = {name for name in sys.modules if name.split(".")[0] in ("torch", "gliner2")}
    GlinerDecideBackend()
    after = {name for name in sys.modules if name.split(".")[0] in ("torch", "gliner2")}
    assert after == before


def test_engine_names_the_requirements_file_when_gliner2_is_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "gliner2", None)
    engine = GlinerDecideEngine(model_id="fastino/GLiNER2.5-Decide", revision="abc", threads=2)
    with pytest.raises(RuntimeError, match="requirements-judge-gliner.txt"):
        engine.ensure_loaded()


def test_schema_strings_avoid_gliner2_reserved_characters():
    reserved = ("(", ")", "[P]", "[L]", "[C]", "[E]", "[R]", "[DESCRIPTION]", "[EXAMPLE]", "[OUTPUT]")
    strings = [gl.SCORE_QUESTION, gl.GROUNDING_QUESTION, gl.PASS_QUESTION, gl.CHOICE_QUESTION]
    strings += list(gl.FAILURE_MODE_DESCRIPTIONS) + list(gl.FAILURE_MODE_DESCRIPTIONS.values())
    strings += list(gl.YES_NO_LABELS[gl.GROUNDED_HEAD].values()) + list(gl.YES_NO_LABELS[gl.PASS_HEAD].values())
    for text in strings:
        for token in reserved:
            assert token not in text, (token, text)
    assert set(gl.FAILURE_MODE_DESCRIPTIONS) == set(SOC_FAILURE_TAXONOMY.values())
