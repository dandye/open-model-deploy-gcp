from pathlib import Path


def test_justfile_contains_jev_recipes():
  justfile_path = Path(__file__).resolve().parent.parent / "Justfile"
  content = justfile_path.read_text(encoding="utf-8")
  assert "eval-soc-jev" in content
  assert "eval-soc-sxs-judge" in content
  assert "--judge-backend" in content


def test_overnight_sweep_supports_judge_backend():
  sweep_path = (
      Path(__file__).resolve().parent.parent
      / "scripts"
      / "run_overnight_sweep.py"
  )
  content = sweep_path.read_text(encoding="utf-8")
  assert "--judge-backend" in content


def test_jev_documentation_exists():
  doc_path = (
      Path(__file__).resolve().parent.parent
      / "docs"
      / "jev_vs_gemini_judge_evaluation.md"
  )
  assert doc_path.exists()
  content = doc_path.read_text(encoding="utf-8")
  assert "Score" in content
  assert "Noul" in content
  assert "Choice" in content
