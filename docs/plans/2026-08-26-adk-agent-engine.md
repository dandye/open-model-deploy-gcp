# ADK Agent for Vertex AI Agent Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a modern Google Agent Development Kit (ADK) agent in `adk_agent/` with configurable Gemma/Gemini backends and deploy it to Vertex AI Agent Engine with native OpenTelemetry Cloud Tracing.

**Architecture:** Build an ADK-native `LlmAgent` in `adk_agent/` supporting explicit Gemma backend targets (Vertex AI dedicated GPU endpoint, Cloud Run serverless GPU, or Gemini/Model Garden). Deploy via `vertexai.preview.reasoning_engines.AdkApp(agent=root_agent, enable_tracing=True)` to stream execution traces into Cloud Trace and Agent Engine Console. Reference upstream `google/adk-python` and `google/agents-cli` as git submodules in `external/`.

**Tech Stack:** Python 3.11+, `google-adk>=2.7.1`, `google-cloud-aiplatform>=1.70.0`, `google-genai>=2.19.0`, `opentelemetry-sdk`, `pytest`, `Justfile`.

**Spec:** [`docs/superpowers/specs/2026-08-26-adk-agent-engine-design.md`](file:///usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/agent_engine/docs/superpowers/specs/2026-08-26-adk-agent-engine-design.md)

## Global Constraints
- Do not use emojis in code, commits, comments, or docstrings.
- Python paths must be relative to repository root.
- All code must follow strict type hints and docstrings.
- Test-driven development with unit tests in `tests/` passing before finishing each task.

---

### Task 1: Submodule and Workspace Environment Setup

**Files:**
- Modify: `.gitmodules`
- Create: `external/adk-python` (submodule)
- Create: `external/agents-cli` (submodule)
- Modify: `pyproject.toml` (if present) / runtime environment verification
- Test: `tests/test_adk_env.py`

**Interfaces:**
- Produces: `external/adk-python` and `external/agents-cli` git submodules; `google-adk>=2.7.1` importable.

- [ ] **Step 1: Write the failing environment and submodule test**

```python
# tests/test_adk_env.py
import subprocess
from pathlib import Path

def test_adk_package_installed():
    import google.adk
    from google.adk.agents import Agent
    assert google.adk.__version__ is not None
    assert Agent is not None

def test_submodules_exist():
    root = Path(__file__).resolve().parent.parent
    adk_dir = root / "external" / "adk-python"
    cli_dir = root / "external" / "agents-cli"
    assert adk_dir.exists()
    assert cli_dir.exists()
```

- [ ] **Step 2: Run test to verify it fails on submodules**

Run: `uv run pytest tests/test_adk_env.py -v`
Expected: FAIL (submodule directories missing)

- [ ] **Step 3: Add submodules and update environment**

```bash
git submodule add https://github.com/google/adk-python.git external/adk-python || true
git submodule add https://github.com/google/agents-cli.git external/agents-cli || true
uv pip install "google-adk>=2.7.1" "google-cloud-aiplatform>=1.70.0" "google-genai>=2.19.0" "opentelemetry-sdk"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_adk_env.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .gitmodules external/ tests/test_adk_env.py
git commit -m "build: add adk-python and agents-cli submodules and verify adk environment"
```

---

### Task 2: Pure Python Tools Implementation

**Files:**
- Create: `adk_agent/tools.py`
- Create: `tests/test_adk_tools.py`

**Interfaces:**
- Produces: `get_current_time() -> str`, `calculate(expression: str) -> str`

- [ ] **Step 1: Write failing tool tests**

```python
# tests/test_adk_tools.py
from adk_agent.tools import get_current_time, calculate

def test_get_current_time_format():
    now_str = get_current_time()
    assert "UTC" in now_str
    assert len(now_str) >= 19

def test_calculate_valid_expressions():
    assert calculate("2 + 2") == "4"
    assert calculate("10 * 5 / 2") == "25.0"
    assert calculate("2 ** 8") == "256"

def test_calculate_disallowed_expressions():
    res = calculate("__import__('os').system('ls')")
    assert "Error" in res or "disallowed" in res.lower()
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_adk_tools.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'adk_agent'`)

- [ ] **Step 3: Implement tools in `adk_agent/tools.py`**

```python
# adk_agent/tools.py
"""Pure Python callables registered as ADK Agent tools."""

from datetime import datetime, timezone

def get_current_time() -> str:
    """Returns the current UTC date and time."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def calculate(expression: str) -> str:
    """Safely evaluates basic mathematical expressions.
    
    Args:
        expression: Mathematical expression (e.g. '24 * 1024 / 4').
    """
    try:
        allowed_chars = set("0123456789+-*/(). %")
        if not all(c in allowed_chars for c in expression):
            return "Error: Expression contains disallowed characters."
        result = eval(expression, {"__builtins__": None}, {})
        return str(result)
    except Exception as e:
        return f"Calculation error: {e}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_adk_tools.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add adk_agent/tools.py tests/test_adk_tools.py
git commit -m "feat(adk_agent): implement pure python tools"
```

---

### Task 3: Configurable Model Backend Layer

**Files:**
- Create: `adk_agent/models.py`
- Create: `tests/test_adk_models.py`

**Interfaces:**
- Consumes: Environment configuration (`GCP_PROJECT_ID`, `GCP_REGION`, `GEMMA_FLAVOR`, `BACKEND_TYPE`).
- Produces: `resolve_model(flavor: str, backend: str, project_id: str, region: str) -> BaseLlm | str`

- [ ] **Step 1: Write failing backend model tests**

```python
# tests/test_adk_models.py
from adk_agent.models import resolve_model, BackendType

def test_resolve_gemini_backend():
    model = resolve_model(flavor="gemini-2.5-flash", backend="gemini")
    assert model == "gemini-2.5-flash"

def test_resolve_vertex_gemma_backend():
    model_obj = resolve_model(flavor="gemma-2-9b-it", backend="vertex_gemma", endpoint_id="123456789")
    assert model_obj is not None

def test_resolve_cloudrun_gemma_backend():
    model_obj = resolve_model(flavor="gemma-2-9b-it", backend="cloudrun_gemma", cloudrun_url="https://gemma-test.run.app")
    assert model_obj is not None
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_adk_models.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'adk_agent.models'`)

- [ ] **Step 3: Implement `adk_agent/models.py`**

Implement model resolution supporting Vertex AI Online Prediction endpoints (vLLM OpenAI compatible interface or Vertex prediction client), Cloud Run URL, and Gemini.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_adk_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add adk_agent/models.py tests/test_adk_models.py
git commit -m "feat(adk_agent): implement configurable model backend layer"
```

---

### Task 4: ADK Agent Factory & Root Agent

**Files:**
- Create: `adk_agent/agent.py`
- Create: `adk_agent/__init__.py`
- Create: `tests/test_adk_agent.py`

**Interfaces:**
- Consumes: `adk_agent.tools`, `adk_agent.models`
- Produces: `create_agent(flavor, backend, ...) -> Agent`, `root_agent: Agent`

- [ ] **Step 1: Write failing agent factory test**

```python
# tests/test_adk_agent.py
from adk_agent.agent import create_agent
from google.adk.agents import BaseAgent

def test_create_agent_instance():
    agent = create_agent(flavor="gemini-2.5-flash", backend="gemini")
    assert isinstance(agent, BaseAgent)
    assert agent.name == "gemma_adk_agent"
    assert len(agent.tools) >= 2
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_adk_agent.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'adk_agent.agent'`)

- [ ] **Step 3: Implement `adk_agent/agent.py` and `adk_agent/__init__.py`**

Configure `LlmAgent` with tools (`get_current_time`, `calculate`), system instruction, and resolved model.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_adk_agent.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add adk_agent/agent.py adk_agent/__init__.py tests/test_adk_agent.py
git commit -m "feat(adk_agent): implement ADK agent factory and root_agent"
```

---

### Task 5: Local Test Runner CLI

**Files:**
- Create: `adk_agent/test_agent.py`
- Create: `tests/test_adk_runner.py`

**Interfaces:**
- Consumes: `adk_agent.agent.create_agent`
- Produces: CLI script accepting prompt, `--flavor`, `--backend`, `--remote` (for deployed Agent Engine querying)

- [ ] **Step 1: Write failing test runner test**

```python
# tests/test_adk_runner.py
from adk_agent.test_agent import run_local_query

def test_run_local_query_gemini():
    # Mocking or executing local test query
    res = run_local_query(prompt="Calculate 15 * 4", flavor="gemini-2.5-flash", backend="gemini")
    assert "60" in res
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_adk_runner.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `adk_agent/test_agent.py`**

Implement local query runner and remote reasoning engine client.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_adk_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add adk_agent/test_agent.py tests/test_adk_runner.py
git commit -m "feat(adk_agent): implement local test runner and remote client"
```

---

### Task 6: Vertex AI Agent Engine Deployment Script & Staging

**Files:**
- Create: `adk_agent/deploy.py`
- Create: `adk_agent/requirements.txt`
- Create: `tests/test_adk_deploy.py`

**Interfaces:**
- Consumes: `adk_agent.agent.create_agent`, `vertexai.preview.reasoning_engines.AdkApp`
- Produces: `deploy(flavor, backend, project_id, region, staging_bucket)`

- [ ] **Step 1: Write failing deployment unit test (mocked)**

```python
# tests/test_adk_deploy.py
from unittest.mock import patch, MagicMock
from adk_agent.deploy import deploy

@patch("vertexai.preview.reasoning_engines.ReasoningEngine.create")
@patch("vertexai.init")
def test_deploy_adk_agent(mock_init, mock_create):
    mock_agent = MagicMock()
    mock_agent.resource_name = "projects/123/locations/us-central1/reasoningEngines/456"
    mock_create.return_value = mock_agent

    result = deploy(flavor="gemma-2-9b-it", backend="gemini", project_id="test-proj")
    assert result == mock_agent
    mock_create.assert_called_once()
    app_arg = mock_create.call_args.kwargs["reasoning_engine"]
    assert app_arg.enable_tracing is True
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/test_adk_deploy.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `adk_agent/deploy.py` and `adk_agent/requirements.txt`**

```python
# adk_agent/deploy.py
import os
import sys
import vertexai
from vertexai.preview import reasoning_engines
from adk_agent.agent import create_agent

def deploy(flavor="gemma-2-9b-it", backend="gemini", project_id=None, region="us-central1", staging_bucket=None):
    project_id = project_id or os.environ.get("GCP_PROJECT_ID", "dandye-0324-chronicle")
    staging_bucket = staging_bucket or os.environ.get("GCS_STAGING_BUCKET", f"gs://{project_id}-agent-engine-staging")

    vertexai.init(project=project_id, location=region, staging_bucket=staging_bucket)
    
    agent = create_agent(flavor=flavor, backend=backend, project_id=project_id, region=region)
    adk_app = reasoning_engines.AdkApp(agent=agent, enable_tracing=True)

    with open(os.path.join(os.path.dirname(__file__), "requirements.txt")) as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    remote_agent = reasoning_engines.ReasoningEngine.create(
        reasoning_engine=adk_app,
        requirements=requirements,
        display_name=f"gemma-adk-{flavor}",
        description="ADK Agent powered by Gemma with Cloud Tracing enabled.",
        extra_packages=["./adk_agent"],
    )
    return remote_agent
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_adk_deploy.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add adk_agent/deploy.py adk_agent/requirements.txt tests/test_adk_deploy.py
git commit -m "feat(adk_agent): implement Agent Engine deployment script with AdkApp tracing"
```

---

### Task 7: Justfile Integration, README Documentation & End-to-End Verification

**Files:**
- Modify: `Justfile`
- Create: `adk_agent/README.md`
- Modify: `GEMINI.md`

**Interfaces:**
- Produces: `just adk-test`, `just adk-deploy`, `just adk-query` recipes; documentation on traces, Cloud Trace navigation, and future dynamic adapter notes.

- [ ] **Step 1: Add Justfile recipes**

Add `adk-test`, `adk-deploy`, `adk-query` recipes to `Justfile`.

- [ ] **Step 2: Create `adk_agent/README.md` and update `GEMINI.md`**

Document usage, parameters, inspecting traces in Google Cloud Console, and the dynamic adapter improvement note.

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add Justfile adk_agent/README.md GEMINI.md
git commit -m "docs: add Justfile recipes and documentation for adk_agent"
```
