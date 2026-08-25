"""Unit tests for Justfile SOC recipes and documentation integration."""

import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_justfile_contains_soc_recipes():
    """Verify Justfile contains agent-soc-test, agent-soc-eval, and agent-soc-deploy recipes."""
    justfile_path = ROOT_DIR / "Justfile"
    assert justfile_path.exists(), "Justfile not found"

    content = justfile_path.read_text(encoding="utf-8")

    # Assert recipe definitions exist
    assert "agent-soc-test" in content, "Recipe 'agent-soc-test' not defined in Justfile"
    assert "agent-soc-eval" in content, "Recipe 'agent-soc-eval' not defined in Justfile"
    assert "agent-soc-deploy" in content, "Recipe 'agent-soc-deploy' not defined in Justfile"

    # Assert recipes are present in the help menu
    assert "just agent-soc-test" in content, "Help menu missing 'just agent-soc-test'"
    assert "just agent-soc-eval" in content, "Help menu missing 'just agent-soc-eval'"
    assert "just agent-soc-deploy" in content, "Help menu missing 'just agent-soc-deploy'"

    # Assert recipes invoke expected Python targets
    assert "deploy_soc_tier1" in content, "Recipe agent-soc-deploy must call deploy_soc_tier1"
    assert "eval_soc_agent" in content, "Recipe agent-soc-eval must call eval_soc_agent"


def test_justfile_syntax():
    """Verify Justfile parses without syntax errors using the just CLI."""
    res = subprocess.run(
        ["just", "--dump"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"Justfile syntax error: {res.stderr}"
    assert "agent-soc-test" in res.stdout
    assert "agent-soc-eval" in res.stdout
    assert "agent-soc-deploy" in res.stdout


def test_experiments_status_contains_track_e():
    """Verify docs/experiments_status.md contains Track E for Gemma SOC evaluation."""
    doc_path = ROOT_DIR / "docs" / "experiments_status.md"
    assert doc_path.exists(), "docs/experiments_status.md not found"

    content = doc_path.read_text(encoding="utf-8")
    assert "Track E: Gemma Model Size vs. SOC Triage Capabilities" in content
    assert "soc_tier1_evalset.json" in content
    assert "gemini-2.5-pro" in content or "LLM-as-a-judge" in content
    assert "gemma-3-1b-it" in content
    assert "gemma-3-4b-it" in content
    assert "gemma-2-9b-it" in content
    assert "gemma-4-31b-it" in content


def test_no_emojis_in_justfile_and_docs():
    """Verify no emojis are present in Justfile, tests, or experiments_status.md."""
    files_to_check = [
        ROOT_DIR / "Justfile",
        ROOT_DIR / "docs" / "experiments_status.md",
        Path(__file__),
    ]
    for fpath in files_to_check:
        text = fpath.read_text(encoding="utf-8")
        for char in text:
            code = ord(char)
            is_emoji = (
                (0x1F600 <= code <= 0x1F64F)
                or (0x1F300 <= code <= 0x1F5FF)
                or (0x1F680 <= code <= 0x1F6FF)
                or (0x1F700 <= code <= 0x1F77F)
                or (0x1F780 <= code <= 0x1F7FF)
                or (0x1F800 <= code <= 0x1F8FF)
                or (0x1F900 <= code <= 0x1F9FF)
                or (0x1FA00 <= code <= 0x1FA6F)
                or (0x1FA70 <= code <= 0x1FAFF)
                or (0x2600 <= code <= 0x26FF)
                or (0x2700 <= code <= 0x27BF)
            )
            assert not is_emoji, f"Emoji character '{char}' (code {code}) found in {fpath.name}"
