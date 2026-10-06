"""GLiNER2.5-Decide backend implementing the Jev primitives on CPU.

The evaluator asks a backend four questions per case (one Score, two Noul
gates, one Choice) over the same serialized state. This backend answers all
four from a single multi-head ``Classifier.classify`` call, cached per state,
so a case costs one forward pass of the deterministic encoder model.

Gate derivation. On 240 reference-policy states the model's own yes/no heads
sat in 0.25-0.50 and ran inverted (a shotgun policy out-scored the oracle on
"grounded"), while the failure-taxonomy head ranked oracle > shotgun >
close_all on every case. The two Noul gates are therefore read off the taxonomy
head and the derivation is reported in ``JevNoulResult.details``:

    pass      = P(FLAWLESS_CONTAINMENT)
    grounding = 1 - P(UNGROUNDED_HALLUCINATED_CLAIM)

The raw yes/no heads are still computed and recorded alongside for diagnostics.

Window. The encoder was trained to 2,048 subword tokens and a few Gen 5
states exceed that. ``fit_state_to_budget`` drops trajectory steps from the
middle outward (first and last steps survive) so the rubric, which comes last
in the state, is never cut. Head truncation would have cut it first.

Dependencies. ``torch`` and ``gliner2`` are imported lazily on first use so
nothing else in the repo pays for them; install them from
``requirements-judge-gliner.txt``. The in-container Harbor verifier keeps its
mock judge and never loads this backend.
"""

from __future__ import annotations

from collections import OrderedDict
import hashlib
import os
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from agent.jev_judge import (
    BaseJevBackend,
    JevChoiceResult,
    JevNoulResult,
    JevScoreResult,
    calculate_expected_score,
)

BACKEND_NAME = "gliner_decide"
DEFAULT_MODEL_ID = "fastino/GLiNER2.5-Decide"
DEFAULT_REVISION = "7ee5da4c2415e32259bcdc0b1a7367c32ce8d6f6"
DEFAULT_THREADS = 8
DEFAULT_TOKEN_BUDGET = 2048
DEFAULT_PASS_THRESHOLD = 0.5
DEFAULT_GROUNDING_THRESHOLD = 0.70
DEFAULT_CACHE_SIZE = 16
JUDGE_REQUIREMENTS_FILE = "requirements-judge-gliner.txt"

SCORE_HEAD = "rubric_score"
GROUNDED_HEAD = "grounded"
PASS_HEAD = "pass"
FAILURE_MODE_HEAD = "failure_mode"
HEADS = (SCORE_HEAD, GROUNDED_HEAD, PASS_HEAD, FAILURE_MODE_HEAD)
SCORE_LEVELS = tuple(str(i) for i in range(11))

PASS_GATE_LABEL = "FLAWLESS_CONTAINMENT"
GROUNDING_GATE_LABEL = "UNGROUNDED_HALLUCINATED_CLAIM"
PASS_GATE_FORMULA = f"P({PASS_GATE_LABEL})"
GROUNDING_GATE_FORMULA = f"1 - P({GROUNDING_GATE_LABEL})"
GROUNDING_KEYWORDS = ("ground", "corroborat", "hallucinat")

# Schema strings. gliner2 rejects "(", ")" and a few bracket tags inside labels,
# descriptions, and instructions, so these are written without them.
SCORE_QUESTION = (
    "On an ordered operational grading scale of 0 to 10, where 0 is total operational "
    "failure and 10 is flawless expert containment, what score does the agent response "
    "earn against the operational grading rubric?"
)
GROUNDING_QUESTION = (
    "Are all claims, IOC classifications, and forensic assertions in the agent response "
    "strictly grounded and corroborated by the actual tool execution trajectory without "
    "hallucination?"
)
PASS_QUESTION = (
    "Did the agent satisfy mandatory SOC triage and containment standards for this "
    "incident without fatal operational errors?"
)
CHOICE_QUESTION = "Which category best describes the agent's primary operational performance or failure mode?"
YES_NO_LABELS: Dict[str, Dict[str, str]] = {
    GROUNDED_HEAD: {
        "yes": "every claim is supported by a tool observation",
        "no": "at least one claim is unsupported",
    },
    PASS_HEAD: {
        "yes": "triage and containment standards were met",
        "no": "a mandatory standard was missed or a fatal error occurred",
    },
}
FAILURE_MODE_DESCRIPTIONS: Dict[str, str] = {
    "FLAWLESS_CONTAINMENT": "the agent investigated with tools, reached the correct verdict, and took exactly the required action",
    "UNGROUNDED_HALLUCINATED_CLAIM": "the agent asserted facts or indicators that the tool observations do not support",
    "MISSED_MALICIOUS_BREACH": "the agent treated a real threat as benign or closed it without containment",
    "OVER_CONTAINMENT_FALSE_ALARM": "the agent isolated hosts or blocked indicators that were benign or outside the required scope",
    "PREMATURE_TERMINATION_ZERO_TOOLS": "the agent stopped without investigating, with zero or no meaningful tool calls",
    "RUNBOOK_PROCEDURAL_VIOLATION": "the agent skipped or reordered mandatory runbook steps or approvals",
    "DEGRADED_MODE_FAILURE": "the agent failed to adapt when a tool was unavailable, slow, or returned errors",
}

# State layout produced by agent.jev_evaluator.build_soc_evaluation_state.
TRAJECTORY_HEADER = "### Actual Tool Execution Trajectory:"
RESPONSE_HEADER = "### Agent Response:"
OMISSION_MARKER = "[... {n} trajectory steps omitted to fit the judge window ...]"
_STEP_LINE = re.compile(r"^Step \S+: Tool ")


def build_classification_schema(schema_cls: Any) -> Any:
    """Registers the four heads on a gliner2 ``ClassificationSchema`` class."""
    return (
        schema_cls()
        .ordinal(SCORE_HEAD, list(SCORE_LEVELS), instruction=SCORE_QUESTION)
        .single(GROUNDED_HEAD, dict(YES_NO_LABELS[GROUNDED_HEAD]), instruction=GROUNDING_QUESTION)
        .single(PASS_HEAD, dict(YES_NO_LABELS[PASS_HEAD]), instruction=PASS_QUESTION)
        .single(FAILURE_MODE_HEAD, dict(FAILURE_MODE_DESCRIPTIONS), instruction=CHOICE_QUESTION)
    )


def _split_trajectory(state: str) -> Optional[Tuple[str, List[str], str]]:
    """Splits a state into (text before the steps, step blocks, text from the response on).

    Returns None when the state has no trimmable trajectory: no tool section,
    the "NO TOOLS WERE INVOKED" sentinel, or fewer than three steps (the first
    and last step always survive, so there is nothing in the middle to drop).
    """
    start = state.find(TRAJECTORY_HEADER)
    end = state.find(RESPONSE_HEADER)
    if start < 0 or end < 0 or end < start:
        return None
    body_start = start + len(TRAJECTORY_HEADER)
    steps: List[str] = []
    for line in state[body_start:end].strip("\n").split("\n"):
        if _STEP_LINE.match(line) or not steps:
            steps.append(line)
        else:
            steps[-1] += "\n" + line
    if len(steps) < 3 or not _STEP_LINE.match(steps[0]):
        return None
    return state[:body_start], steps, state[end:]


def fit_state_to_budget(
    state: str, count_tokens: Callable[[str], int], token_budget: int
) -> Tuple[str, Dict[str, Any]]:
    """Drops middle trajectory steps until ``state`` fits ``token_budget`` tokens.

    Returns the (possibly trimmed) state and a dict with ``tokens_before``,
    ``tokens_after``, ``steps_omitted`` and ``within_budget``. States already
    inside the budget are returned verbatim. When even the first-plus-last
    trajectory does not fit, the most trimmed form is returned and
    ``within_budget`` is False; the rubric is never cut.
    """
    tokens_before = count_tokens(state)
    info: Dict[str, Any] = {
        "tokens_before": tokens_before,
        "tokens_after": tokens_before,
        "steps_omitted": 0,
        "within_budget": tokens_before <= token_budget,
    }
    if info["within_budget"]:
        return state, info
    parts = _split_trajectory(state)
    if parts is None:
        return state, info
    head, steps, tail = parts
    n_steps = len(steps)
    fitted = state
    for omitted in range(1, n_steps - 1):
        kept = n_steps - omitted
        keep_head = (kept + 1) // 2
        keep_tail = kept - keep_head
        blocks = steps[:keep_head] + [OMISSION_MARKER.format(n=omitted)] + steps[n_steps - keep_tail:]
        fitted = head + "\n" + "\n".join(blocks) + "\n\n" + tail
        tokens_after = count_tokens(fitted)
        info.update(
            tokens_after=tokens_after,
            steps_omitted=omitted,
            within_budget=tokens_after <= token_budget,
        )
        if info["within_budget"]:
            break
    return fitted, info


def _find_tokenizer(extractor: Any) -> Optional[Callable[..., Any]]:
    for path in ("processor.tokenizer", "tokenizer", "model.processor.tokenizer"):
        obj = extractor
        try:
            for part in path.split("."):
                obj = getattr(obj, part)
        except AttributeError:
            continue
        if callable(obj):
            return obj
    return None


class GlinerDecideEngine:
    """Owns the model: lazy load, one multi-head classify per text, token counting."""

    def __init__(self, model_id: str, revision: str, threads: int):
        self.model_id = model_id
        self.revision = revision
        self.threads = threads
        self._classifier: Any = None
        self._schema: Any = None
        self._config: Any = None
        self._tokenizer: Optional[Callable[..., Any]] = None

    def ensure_loaded(self) -> None:
        if self._classifier is not None:
            return
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        try:
            from gliner2 import AutoExtractor
            from gliner2.classification import ClassificationConfig, ClassificationSchema, Classifier
            import torch
        except ImportError as exc:
            raise RuntimeError(
                "--jev-backend gliner_decide needs the optional judge dependencies "
                f"(torch, gliner2). Install them with: uv pip install --python "
                f".venv/bin/python -r {JUDGE_REQUIREMENTS_FILE}"
            ) from exc
        if self.threads > 0:
            torch.set_num_threads(self.threads)
        extractor = AutoExtractor.from_pretrained(self.model_id, revision=self.revision)
        classifier = Classifier(extractor)
        if hasattr(classifier, "eval"):
            classifier.eval()
        self._classifier = classifier
        self._schema = build_classification_schema(ClassificationSchema)
        self._config = ClassificationConfig(include_confidence=True)
        self._tokenizer = _find_tokenizer(extractor)

    def classify_heads(self, text: str) -> Dict[str, Dict[str, float]]:
        self.ensure_loaded()
        import torch

        with torch.inference_mode():
            result = self._classifier.classify(text, self._schema, config=self._config)
        return {
            head: {str(label): float(prob) for label, prob in result.probabilities(head).items()}
            for head in HEADS
        }

    def count_tokens(self, text: str) -> int:
        self.ensure_loaded()
        if self._tokenizer is None:
            return int(len(text.split()) * 1.5)
        return len(self._tokenizer(text, add_special_tokens=False)["input_ids"])


class GlinerDecideBackend(BaseJevBackend):
    """Jev primitives served by one cached GLiNER2.5-Decide classification per state."""

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL_ID,
        revision: str = DEFAULT_REVISION,
        threads: int = DEFAULT_THREADS,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
        pass_threshold: float = DEFAULT_PASS_THRESHOLD,
        grounding_threshold: float = DEFAULT_GROUNDING_THRESHOLD,
        engine: Optional[Any] = None,
        cache_size: int = DEFAULT_CACHE_SIZE,
    ):
        self.model_id = model_id
        self.revision = revision
        self.threads = threads
        self.token_budget = token_budget
        self.pass_threshold = pass_threshold
        self.grounding_threshold = grounding_threshold
        self.cache_size = max(1, cache_size)
        self._engine = engine
        self._cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self.fit_stats: Dict[str, int] = {"states_judged": 0, "states_trimmed": 0, "states_over_budget": 0}

    @property
    def engine(self) -> Any:
        if self._engine is None:
            self._engine = GlinerDecideEngine(self.model_id, self.revision, self.threads)
        return self._engine

    def describe(self) -> Dict[str, Any]:
        """Static judge provenance for run metadata and pre-registration pins."""
        return {
            "backend": BACKEND_NAME,
            "model_id": self.model_id,
            "revision": self.revision,
            "token_budget": self.token_budget,
            "threads": self.threads,
            "pass_threshold": self.pass_threshold,
            "grounding_threshold": self.grounding_threshold,
            "heads": list(HEADS),
            "gates": {"pass": PASS_GATE_FORMULA, "grounding": GROUNDING_GATE_FORMULA},
        }

    def _judge(self, state: str) -> Dict[str, Any]:
        key = hashlib.sha256(state.encode("utf-8")).hexdigest()
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached
        fitted, fit_info = fit_state_to_budget(state, self.engine.count_tokens, self.token_budget)
        entry = {"heads": self.engine.classify_heads(fitted), "fit": fit_info}
        self.fit_stats["states_judged"] += 1
        if fit_info["steps_omitted"]:
            self.fit_stats["states_trimmed"] += 1
        if not fit_info["within_budget"]:
            self.fit_stats["states_over_budget"] += 1
        self._cache[key] = entry
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)
        return entry

    def evaluate_score(self, state: str, num_levels: int = 10) -> JevScoreResult:
        if num_levels != 10:
            raise ValueError(
                f"GlinerDecideBackend scores on a fixed 0-10 ordinal head; num_levels={num_levels} is not supported"
            )
        probs = self._judge(state)["heads"][SCORE_HEAD]
        level_probs = {int(level): float(probs.get(level, 0.0)) for level in SCORE_LEVELS}
        raw_level = max(level_probs.items(), key=lambda kv: kv[1])[0]
        return JevScoreResult(
            expected_score=calculate_expected_score(level_probs, scale_factor=10.0),
            level_probs=level_probs,
            raw_level=raw_level,
        )

    def evaluate_noul(self, state: str, question: str) -> JevNoulResult:
        entry = self._judge(state)
        taxonomy = entry["heads"][FAILURE_MODE_HEAD]
        if any(keyword in question.lower() for keyword in GROUNDING_KEYWORDS):
            probability = 1.0 - float(taxonomy.get(GROUNDING_GATE_LABEL, 0.0))
            threshold, formula, raw_head = self.grounding_threshold, GROUNDING_GATE_FORMULA, GROUNDED_HEAD
        else:
            probability = float(taxonomy.get(PASS_GATE_LABEL, 0.0))
            threshold, formula, raw_head = self.pass_threshold, PASS_GATE_FORMULA, PASS_HEAD
        probability = round(min(max(probability, 0.0), 1.0), 6)
        raw_p_yes = entry["heads"].get(raw_head, {}).get("yes")
        details = {
            "source_head": FAILURE_MODE_HEAD,
            "formula": formula,
            "threshold": threshold,
            "raw_head": raw_head,
            "raw_head_p_yes": None if raw_p_yes is None else float(raw_p_yes),
            "state_fit": dict(entry["fit"]),
        }
        return JevNoulResult(probability=probability, verdict=probability >= threshold, details=details)

    def evaluate_choice(self, state: str, question: str, options: Dict[str, str]) -> JevChoiceResult:
        labels = list(options.values())
        if set(labels) != set(FAILURE_MODE_DESCRIPTIONS):
            raise ValueError(
                "GlinerDecideBackend classifies the fixed SOC failure taxonomy "
                f"{sorted(FAILURE_MODE_DESCRIPTIONS)}; got options {sorted(labels)}"
            )
        probs = self._judge(state)["heads"][FAILURE_MODE_HEAD]
        candidate_probs = {label: float(probs.get(label, 0.0)) for label in labels}
        selected = max(candidate_probs.items(), key=lambda kv: kv[1])[0]
        return JevChoiceResult(selected=selected, candidate_probs=candidate_probs)
