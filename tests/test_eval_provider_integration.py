"""Regression checks for combining main's MCP provider with runbook evaluation."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.eval_soc_agent import main, run_evaluation


def test_cli_forwards_explicit_mcp_provider(tmp_path: Path):
    dataset = tmp_path / "dataset.json"
    dataset.write_text(json.dumps({"generation": 3, "eval_cases": []}))
    output = tmp_path / "result.json"
    with patch("sys.argv", ["eval_soc_agent", "--evalset", str(dataset),
                            "--mcp-provider", "gepa", "--output-json", str(output)]), \
         patch("scripts.eval_soc_agent.run_evaluation", return_value={"summary": {}, "case_results": []}) as evaluate:
        main()
    assert evaluate.call_args.kwargs["mcp_provider"] == "gepa"
    assert evaluate.call_args.kwargs["agent_mode"] == "single"
    assert output.exists()


def test_unsupported_hierarchical_provider_is_explicit():
    with pytest.raises(ValueError, match="single-agent mode"):
        run_evaluation(Path("unused.json"), "fixture", agent_mode="hierarchical", mcp_provider="gepa")
