"""Tests for clean and noisy SOC Tier 1 triage skills used in Harbor evaluations."""

from pathlib import Path
from agent.gepa_runbook_optimizer import validate_runbook_candidate

ROOT_DIR = Path(__file__).resolve().parent.parent
CLEAN_SKILL_PATH = ROOT_DIR / "skills" / "secops-triage" / "SKILL.md"
NOISY_SKILL_PATH = ROOT_DIR / "skills" / "secops-triage" / "noisy" / "verbose_lore.md"


def test_clean_and_noisy_soc_skills_exist_and_pass_anti_memorization():
    """Verify both skill files exist, have frontmatter, and pass anti-memorization checks."""
    assert CLEAN_SKILL_PATH.exists(), f"Missing clean skill at {CLEAN_SKILL_PATH}"
    assert NOISY_SKILL_PATH.exists(), f"Missing noisy skill at {NOISY_SKILL_PATH}"

    clean_text = CLEAN_SKILL_PATH.read_text(encoding="utf-8")
    noisy_text = NOISY_SKILL_PATH.read_text(encoding="utf-8")

    assert clean_text.startswith("---\nname: secops-triage")
    assert "isolate_host" in clean_text
    assert "epistemic" in clean_text.lower()
    assert "503" in clean_text

    # Verify neither skill leaks eval case IDs, hostnames, or raw IPv4 literals
    is_valid, violations = validate_runbook_candidate({
        "clean_skill.md": clean_text,
        "noisy_skill.md": noisy_text,
    })
    assert is_valid, f"Skill anti-memorization violations: {violations}"

    # Noisy skill must be substantially longer verbose prose to test verbosity bias
    assert len(noisy_text) >= int(len(clean_text) * 2.0)
