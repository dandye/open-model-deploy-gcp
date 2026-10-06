"""The Gen 5 campaign judge is pinned in one place and the Gen 5 recipes carry it."""

import json
from pathlib import Path
from typing import List

from agent.jev_backend_gliner import GlinerDecideBackend

ROOT_DIR = Path(__file__).resolve().parent.parent
JUSTFILE = ROOT_DIR / "Justfile"
CAMPAIGN = ROOT_DIR / "configs" / "experiments" / "gen5_campaign1.json"


def recipe_body(name: str) -> str:
    lines = JUSTFILE.read_text(encoding="utf-8").splitlines()
    body: List[str] = []
    capturing = False
    for line in lines:
        if not capturing and (line.startswith(f"{name} ") or line.startswith(f"{name}:")):
            capturing = True
            continue
        if capturing:
            if line and not line[0].isspace():
                break
            body.append(line)
    assert capturing, f"recipe {name} not found in Justfile"
    return "\n".join(body)


def test_gen5_runner_recipes_select_the_gliner_judge():
    for name in ("eval-gen5", "gen5-gradient"):
        assert "--jev-backend gliner_decide" in recipe_body(name), name


def test_gen5_optimizer_recipes_select_the_gliner_judge():
    for name in ("gen5-noise", "gepa-evolve"):
        body = recipe_body(name)
        assert "--judge-backend jev" in body, name
        assert "--jev-backend gliner_decide" in body, name


def test_gen5_calibrate_recipe_keeps_mock_by_default_but_can_run_the_real_judge():
    header = next(line for line in JUSTFILE.read_text(encoding="utf-8").splitlines() if line.startswith("gen5-calibrate"))
    assert 'JEV_BACKEND="mock"' in header
    assert "--jev-backend {{JEV_BACKEND}}" in recipe_body("gen5-calibrate")


def test_gen3_recipes_keep_the_gemini_default():
    for name in ("eval-gen3", "eval-gen3-live"):
        assert "gliner_decide" not in recipe_body(name), name


def test_preregistration_pins_the_judge_to_the_backend_constants():
    data = json.loads(CAMPAIGN.read_text(encoding="utf-8"))
    pin = data["gen5"]["judge"]
    assert pin["judge_backend"] == "jev"
    assert pin["jev_backend"] == "gliner_decide"
    described = GlinerDecideBackend().describe()
    for key in ("model_id", "revision", "token_budget", "threads", "pass_threshold", "grounding_threshold", "gates"):
        assert pin[key] == described[key], key
    assert pin["deterministic"] is True
    assert "gliner_decide" in data["gen5"]["comparison"]["scorer"]
