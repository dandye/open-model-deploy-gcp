"""Gemini System-1 Logprobs Backend implementing Jev primitives."""

import math
import os
from typing import Dict, List, Optional
from google import genai
from google.genai import types

from agent.jev_judge import (
    BaseJevBackend,
    JevChoiceResult,
    JevNoulResult,
    JevScoreResult,
    calculate_expected_score,
    normalize_noul_probs,
)


class GeminiSystem1Backend(BaseJevBackend):
    """Executes Jev primitives using Gemini logprobs, constrained enums, and minimal thinking."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: str = "us-central1",
        model: str = "gemini-2.5-flash",
        client: Optional[genai.Client] = None,
    ):
        resolved_project = (
            project_id
            or os.environ.get("GCP_PROJECT_ID")
            or os.environ.get("PROJECT_ID")
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
            or ""
        )
        self.project_id = resolved_project
        self.location = location
        self.model = model
        self.client = client or genai.Client(
            vertexai=True, project=self.project_id, location=self.location
        )

    def _sample_logprobs_enum(
        self, prompt: str, enum_values: List[str]
    ) -> Dict[str, float]:
        """Calls Gemini API with constrained enum and logprobs, returning candidate probabilities."""
        config = types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=5,
            response_mime_type="text/x.enum",
            response_schema=types.Schema(
                type=types.Type.STRING,
                enum=enum_values,
            ),
            response_logprobs=True,
            thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
        )
        res = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )

        probs: Dict[str, float] = {}
        candidate = res.candidates[0] if res.candidates else None
        if not candidate or not candidate.logprobs_result:
            chosen = (res.text or "").strip()
            return {val: (1.0 if val == chosen else 0.0) for val in enum_values}

        top_cands = candidate.logprobs_result.top_candidates
        target_step = top_cands[-1] if top_cands else []
        step_items = getattr(target_step, "candidates", target_step) or []
        logprob_map = {
            c.token.strip(): c.log_probability for c in step_items if getattr(c, "token", None)
        }

        exp_sum = 0.0
        exp_vals: Dict[str, float] = {}
        for val in enum_values:
            lp = logprob_map.get(val, -20.0)
            e = math.exp(lp)
            exp_vals[val] = e
            exp_sum += e

        for val in enum_values:
            probs[val] = (
                exp_vals[val] / exp_sum
                if exp_sum > 0.0
                else (1.0 / len(enum_values))
            )

        return probs

    def evaluate_score(self, state: str, num_levels: int = 10) -> JevScoreResult:
        enum_levels = [str(i) for i in range(num_levels + 1)]
        prompt = f"""State:
{state}

Question: On an ordered operational grading scale of 0 to {num_levels} (where 0 is total operational failure and {num_levels} is flawless expert containment), what score does this response earn?
Reply with a single digit from 0 to {num_levels}."""
        probs_str = self._sample_logprobs_enum(prompt, enum_levels)
        probs_int = {int(k): v for k, v in probs_str.items() if k.isdigit()}
        exp_score = calculate_expected_score(probs_int, scale_factor=10.0)
        best_level = (
            max(probs_int.items(), key=lambda x: x[1])[0] if probs_int else 0
        )
        return JevScoreResult(
            expected_score=exp_score, level_probs=probs_int, raw_level=best_level
        )

    def evaluate_noul(self, state: str, question: str) -> JevNoulResult:
        prompt = f"""State:
{state}

Question: {question}
Reply with YES or NO."""
        probs = self._sample_logprobs_enum(prompt, ["YES", "NO"])
        p_yes = probs.get("YES", 0.5)
        return JevNoulResult(probability=p_yes, verdict=p_yes >= 0.70)

    def evaluate_choice(
        self, state: str, question: str, options: Dict[str, str]
    ) -> JevChoiceResult:
        keys = list(options.keys())
        options_text = "\n".join(f"{k}: {desc}" for k, desc in options.items())
        prompt = f"""State:
{state}

Question: {question}
Options:
{options_text}

Reply with the single option letter."""
        probs = self._sample_logprobs_enum(prompt, keys)
        best_key = max(probs.items(), key=lambda x: x[1])[0] if probs else keys[0]
        labeled_probs = {options[k]: probs.get(k, 0.0) for k in keys}
        return JevChoiceResult(
            selected=options[best_key], candidate_probs=labeled_probs
        )
