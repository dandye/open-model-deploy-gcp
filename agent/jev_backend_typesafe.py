"""TypeSafe AI Jev Remote HTTP Client Backend."""

import json
import os
from typing import Any, Dict, Optional
import urllib.error
import urllib.request

from agent.jev_judge import (
    BaseJevBackend,
    JevChoiceResult,
    JevNoulResult,
    JevScoreResult,
)


class TypeSafeJevBackend(BaseJevBackend):
    """Executes Jev primitives via TypeSafe AI System One REST API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint_url: str = "https://api.typesafe.ai/v1/systemone",
    ):
        self.api_key = (
            api_key
            or os.environ.get("TYPE_SAFE_API_KEY")
            or os.environ.get("JEV_API_KEY", "")
        )
        self.endpoint_url = endpoint_url

    def _post_systemone(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Sends POST request to TypeSafe System One API."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint_url, data=data, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(
                f"TypeSafe Jev API HTTP Error {e.code}: {e.read().decode('utf-8')}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"TypeSafe Jev API request failed: {e}") from e

    def evaluate_score(self, state: str, num_levels: int = 10) -> JevScoreResult:
        payload = {
            "state": state,
            "questions": [
                {
                    "primitive": "score",
                    "rubric_levels": num_levels,
                }
            ],
        }
        res = self._post_systemone(payload)
        item = res.get("results", [{}])[0]
        exp_val = float(item.get("expected_value", 0.0))
        dist = {int(k): float(v) for k, v in item.get("distribution", {}).items()}
        return JevScoreResult(
            expected_score=round(exp_val * 10.0, 2),
            level_probs=dist,
            raw_level=int(round(exp_val)),
        )

    def evaluate_noul(self, state: str, question: str) -> JevNoulResult:
        payload = {
            "state": state,
            "questions": [
                {
                    "primitive": "noul",
                    "question": question,
                }
            ],
        }
        res = self._post_systemone(payload)
        item = res.get("results", [{}])[0]
        prob = float(item.get("probability", 0.5))
        return JevNoulResult(probability=prob, verdict=prob >= 0.70)

    def evaluate_choice(
        self, state: str, question: str, options: Dict[str, str]
    ) -> JevChoiceResult:
        payload = {
            "state": state,
            "questions": [
                {
                    "primitive": "choice",
                    "question": question,
                    "candidates": list(options.values()),
                }
            ],
        }
        res = self._post_systemone(payload)
        item = res.get("results", [{}])[0]
        selected = str(item.get("selected", next(iter(options.values()))))
        cand_probs = {
            str(k): float(v) for k, v in item.get("candidate_probs", {}).items()
        }
        return JevChoiceResult(selected=selected, candidate_probs=cand_probs)
