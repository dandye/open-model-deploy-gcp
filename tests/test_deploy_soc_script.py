"""Tests for SOC Tier 1 Agent Engine deployment script."""

from pathlib import Path
import re
from unittest.mock import MagicMock, patch
from agent.deploy_soc_tier1 import deploy, get_deployment_config


def test_deployment_config():
    cfg = get_deployment_config()
    assert "display_name" in cfg
    assert cfg["display_name"] == "gemma-soc-tier1-agent"
    assert "description" in cfg
    assert "SOC" in cfg["description"]
    assert "requirements" in cfg
    assert isinstance(cfg["requirements"], list)
    assert any("google-cloud-aiplatform" in req for req in cfg["requirements"])
    assert any("google-genai" in req for req in cfg["requirements"])
    assert any("pydantic" in req for req in cfg["requirements"])
    assert any("requests" in req for req in cfg["requirements"])


@patch("agent.deploy_soc_tier1.vertexai.init")
@patch("agent.deploy_soc_tier1.reasoning_engines.ReasoningEngine.create")
def test_deploy_soc_tier1_mocked(mock_engine_create, mock_vertexai_init):
    mock_remote_engine = MagicMock()
    mock_remote_engine.resource_name = (
        "projects/12345/locations/us-central1/reasoningEngines/67890"
    )
    mock_engine_create.return_value = mock_remote_engine

    result = deploy()

    assert result == mock_remote_engine
    mock_vertexai_init.assert_called_once()
    mock_engine_create.assert_called_once()

    _, kwargs = mock_engine_create.call_args
    assert kwargs["display_name"] == "gemma-soc-tier1-agent"
    assert "SOC" in kwargs["description"]
    assert isinstance(kwargs["requirements"], list)
    assert kwargs["reasoning_engine"] is not None


def test_no_emojis_in_deploy_script():
    script_path = Path("agent/deploy_soc_tier1.py")
    assert script_path.exists()
    content = script_path.read_text(encoding="utf-8")

    emoji_pattern = re.compile(
        "[\U00010000-\U0010ffff]",
        flags=re.UNICODE,
    )
    assert not emoji_pattern.search(content), "Emojis found in deploy_soc_tier1.py"
