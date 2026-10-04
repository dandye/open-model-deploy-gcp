"""Core Jev (System One) primitives, data models, and backend interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import math
from typing import Any, Dict


@dataclass(frozen=True)
class JevScoreResult:
    """Output for a Jev Score primitive (ordered rubric expected value)."""

    expected_score: float
    level_probs: Dict[int, float]
    raw_level: int


@dataclass(frozen=True)
class JevNoulResult:
    """Output for a Jev Noul primitive (calibrated boolean probability)."""

    probability: float
    verdict: bool


@dataclass(frozen=True)
class JevChoiceResult:
    """Output for a Jev Choice primitive (categorical classification)."""

    selected: str
    candidate_probs: Dict[str, float]


@dataclass
class JevEvaluationOutput:
    """Consolidated Jev evaluation result matching SOC judge contract."""

    rubric_score: float
    passed: bool
    grounding_score: float
    primary_choice: str
    critique: str
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


def normalize_noul_probs(logprob_yes: float, logprob_no: float) -> float:
    """Renormalizes log probabilities over {YES, NO} into calibrated P(YES)."""
    max_lp = max(logprob_yes, logprob_no)
    exp_yes = math.exp(logprob_yes - max_lp)
    exp_no = math.exp(logprob_no - max_lp)
    total = exp_yes + exp_no
    return exp_yes / total if total > 0.0 else 0.5


def calculate_expected_score(
    level_probs: Dict[int, float], scale_factor: float = 10.0
) -> float:
    """Computes expected value sum(k * p_k) scaled to target score range."""
    exp_val = sum(float(k) * float(p) for k, p in level_probs.items())
    return round(exp_val * scale_factor, 2)


class BaseJevBackend(ABC):
    """Abstract interface for Jev System One evaluation backends."""

    @abstractmethod
    def evaluate_score(self, state: str, num_levels: int = 10) -> JevScoreResult:
        """Evaluates an ordered rubric score primitive."""

    @abstractmethod
    def evaluate_noul(self, state: str, question: str) -> JevNoulResult:
        """Evaluates a calibrated boolean probability primitive."""

    @abstractmethod
    def evaluate_choice(
        self, state: str, question: str, options: Dict[str, str]
    ) -> JevChoiceResult:
        """Evaluates a categorical choice primitive."""


class MockJevBackend(BaseJevBackend):
    """Deterministic mock backend for testing and hermetic evaluation."""

    def __init__(
        self,
        score_level: int = 8,
        noul_pass_prob: float = 0.85,
        noul_grounding_prob: float = 0.90,
        choice_label: str = "FLAWLESS_CONTAINMENT",
    ):
        self.score_level = score_level
        self.noul_pass_prob = noul_pass_prob
        self.noul_grounding_prob = noul_grounding_prob
        self.choice_label = choice_label

    def evaluate_score(self, state: str, num_levels: int = 10) -> JevScoreResult:
        probs = {self.score_level: 1.0}
        return JevScoreResult(
            expected_score=float(self.score_level * 10),
            level_probs=probs,
            raw_level=self.score_level,
        )

    def evaluate_noul(self, state: str, question: str) -> JevNoulResult:
        q_lower = question.lower()
        is_grounding = any(
            kw in q_lower for kw in ("ground", "corroborat", "hallucinat")
        )
        prob = self.noul_grounding_prob if is_grounding else self.noul_pass_prob
        return JevNoulResult(probability=prob, verdict=prob >= 0.70)

    def evaluate_choice(
        self, state: str, question: str, options: Dict[str, str]
    ) -> JevChoiceResult:
        selected = (
            self.choice_label
            if self.choice_label in options.values()
            else next(iter(options.values()))
        )
        probs = {opt: (1.0 if opt == selected else 0.0) for opt in options.values()}
        return JevChoiceResult(selected=selected, candidate_probs=probs)
