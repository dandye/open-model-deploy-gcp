# Benchmark Expansion Phase 1: Ambiguous & Resilient SOC Triage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the SOC Tier 1 evaluation benchmark suite from 5 to 10 cases by introducing ambiguous threat signals, tool error simulation, lateral movement correlation, supply chain risk indicators, and true negative scanner traffic, alongside enriched mock tool implementations.

**Architecture:** Enrich `agent/soc_tools.py` to support parameterized responses, borderline reputation data, lateral movement telemetry, supply chain certificate metadata, and HTTP 503 error simulation. Update `configs/evals/soc_tier1_triage.json` with 5 new discriminative evaluation cases (CASE-06 through CASE-10) with tailored rubrics and deterministic assertions. Update `scripts/eval_soc_agent.py` and `agent/soc_tier1_agent.py` to handle error payloads and evaluate tool resilience.

**Tech Stack:** Python 3.10+, pytest, pydantic, Google GenAI SDK (Gemini 2.5 Pro as LLM Judge).

**Spec:** [`benchmark_expansion_proposal.md`](file:///usr/local/google/home/dandye/.gemini/jetski/brain/8044d9a1-fda6-4da8-a4ef-ed7881dbe9cd/benchmark_expansion_proposal.md)

## Global Constraints

- Strictly NO EMOJIS anywhere in code, comments, docstrings, commits, or tests.
- Explicit shell and python variable definitions.
- Worktree-relative path resolution (`ROOT_DIR = Path(__file__).resolve().parent.parent`).
- Backward compatibility: Existing 5 evaluation cases (`CASE-01` through `CASE-05`) must continue to pass identically.
- Hermetic tests: Unit tests must run locally and offline without external network dependencies.

---

### Task 1: Enriched Mock Tools with Parameterized Data & Failure Simulation

**Files:**
- Modify: `agent/soc_tools.py:1-125`
- Test: `tests/test_soc_tools.py:1-117`

**Interfaces:**
- Consumes: Indicator strings (IPs, domains, hashes, entity IDs).
- Produces: JSON strings with enriched categories, borderline reputation metrics, error payloads, and multi-entity links.
  - `get_domain_report("tunnel-data.cdn-edge-update.net")` -> returns borderline verdict `BORDERLINE_SUSPICIOUS`, `category: "Dynamic DNS / CDN Tunnel"`, `malicious_votes: 18`, `harmless_votes: 22`.
  - `get_domain_report("error-503.service-unavailable.org")` -> returns `{"error": "HTTP 503: Upstream Threat Intelligence Service Unavailable", "status_code": 503, "domain": "error-503.service-unavailable.org"}`.
  - `lookup_entity("10.0.8.99")` or `lookup_entity("DESKTOP-HR-04")` -> returns lateral movement indicators with `recent_event_types: ["VPN_AUTHENTICATION", "PROCESS_LAUNCH", "SMB_SESSION"]`, `process_command: "psexec.exe -u admin -p ... \\\\10.0.8.99 cmd.exe"`.
  - `get_file_report("a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90")` -> returns `verdict: "SUSPICIOUS"`, `threat_name: "Signed.SupplyChain.Anomaly"`, `certificate_status: "REVOKED_CERTIFICATE"`, `vendor: "Acme Corp (Compromised Signing Key)"`.
  - `get_ip_address_report("10.0.99.50")` -> returns `category: "Internal Authorized Scanner"`, `reputation: "BENIGN_AUTHORIZED"`, `verdict: "SAFE"`, `service: "Qualys Vulnerability Scanner"`.

- [ ] **Step 1: Write failing unit tests for new mock tool behaviors**

```python
# In tests/test_soc_tools.py:
def test_domain_report_borderline_dns_tunnel():
    """Verify borderline DNS tunnel domain returns calibrated ambiguous metrics."""
    raw = get_domain_report("tunnel-data.cdn-edge-update.net")
    data = json.loads(raw)
    assert data["domain"] == "tunnel-data.cdn-edge-update.net"
    assert data["verdict"] == "BORDERLINE_SUSPICIOUS"
    assert data["malicious_votes"] == 18
    assert data["harmless_votes"] == 22
    assert "CDN Tunnel" in data["category"]


def test_domain_report_error_simulation():
    """Verify HTTP 503 simulated service outage returns error payload."""
    raw = get_domain_report("error-503.service-unavailable.org")
    data = json.loads(raw)
    assert data["status_code"] == 503
    assert "HTTP 503" in data["error"]
    assert data["domain"] == "error-503.service-unavailable.org"


def test_lookup_entity_lateral_movement():
    """Verify lateral movement telemetry indicators in entity lookup."""
    raw = lookup_entity("DESKTOP-HR-04")
    data = json.loads(raw)
    assert data["entity"] == "DESKTOP-HR-04"
    assert data["suspicious_indicators"] is True
    assert "psexec" in data["process_command"].lower()
    assert "10.0.8.99" in data["target_host"]


def test_file_report_supply_chain_revoked_cert():
    """Verify supply chain file hash returns revoked certificate metadata."""
    sha256_hash = "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"
    raw = get_file_report(sha256_hash)
    data = json.loads(raw)
    assert data["hash"] == sha256_hash
    assert data["certificate_status"] == "REVOKED_CERTIFICATE"
    assert "SupplyChain" in data["threat_name"]
    assert "Acme Corp" in data["vendor"]


def test_ip_report_authorized_scanner():
    """Verify authorized vulnerability scanner IP returns benign authorized status."""
    raw = get_ip_address_report("10.0.99.50")
    data = json.loads(raw)
    assert data["ip"] == "10.0.99.50"
    assert data["verdict"] == "SAFE"
    assert "Authorized Scanner" in data["category"]
```

- [ ] **Step 2: Run pytest to verify new tests fail**

Run: `/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/main/.venv/bin/pytest -v tests/test_soc_tools.py`
Expected: FAIL on new test functions.

- [ ] **Step 3: Implement new tool behaviors in `agent/soc_tools.py`**

Update `agent/soc_tools.py` to support the new indicators, borderline calculations, certificate revocation fields, and HTTP 503 error payloads while preserving all existing indicator paths.

- [ ] **Step 4: Run pytest to verify all tests pass**

Run: `/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/main/.venv/bin/pytest -v tests/test_soc_tools.py`
Expected: PASS (all tests green).

- [ ] **Step 5: Commit changes**

```bash
git add agent/soc_tools.py tests/test_soc_tools.py
git commit -m "feat(soc-tools): add parameterized mock tools with borderline signals and error simulation"
```

---

### Task 2: Expand Evaluation Suite to 10 Cases in `configs/evals/soc_tier1_triage.json`

**Files:**
- Modify: `configs/evals/soc_tier1_triage.json`
- Test: `tests/test_eval_config_schema.py`

**Interfaces:**
- Consumes: JSON test cases schema with `eval_id`, `name`, `prompt`, `reference`, `assertions`.
- Produces: 10 structured benchmark cases covering:
  - `CASE-01-LOKIBOT-C2`: Baseline info-stealer triage (Existing).
  - `CASE-02-RFC5737-BENIGN-IP`: Reserved documentation grounding test (Existing).
  - `CASE-03-PHISHING-CRED-HARVEST`: Phishing credential harvesting triage (Existing).
  - `CASE-04-DUPLICATE-SOAR-CASE`: Duplicate case detection (Existing).
  - `CASE-05-RANSOMWARE-ESCALATION`: Critical ransomware containment (Existing).
  - `CASE-06-AMBIGUOUS-DNS-TUNNEL`: Borderline 45%/55% reputation CDN tunnel (New).
  - `CASE-07-LATERAL-MOVEMENT`: Internal lateral movement with PsExec correlation (New).
  - `CASE-08-SUPPLY-CHAIN-REVOKED-CERT`: Vendor software update with revoked cert (New).
  - `CASE-09-TOOL-FAILURE-RESILIENCE`: HTTP 503 threat intel service outage handling (New).
  - `CASE-10-AUTHORIZED-SCANNER-TRUE-NEGATIVE`: Internal vulnerability scanner noise triage (New).

- [ ] **Step 1: Write test for 10-case evaluation suite schema completeness**

```python
# In tests/test_eval_config_schema.py:
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_eval_suite_contains_ten_cases():
    """Verify configs/evals/soc_tier1_triage.json contains exactly 10 valid cases."""
    config_path = ROOT_DIR / "configs" / "evals" / "soc_tier1_triage.json"
    assert config_path.exists()
    data = json.loads(config_path.read_text())
    assert data["evalset_id"] == "soc_tier1_triage"
    assert len(data["eval_cases"]) == 10

    case_ids = [c["eval_id"] for c in data["eval_cases"]]
    expected_ids = [
        "CASE-01-LOKIBOT-C2",
        "CASE-02-RFC5737-BENIGN-IP",
        "CASE-03-PHISHING-CRED-HARVEST",
        "CASE-04-DUPLICATE-SOAR-CASE",
        "CASE-05-RANSOMWARE-ESCALATION",
        "CASE-06-AMBIGUOUS-DNS-TUNNEL",
        "CASE-07-LATERAL-MOVEMENT",
        "CASE-08-SUPPLY-CHAIN-REVOKED-CERT",
        "CASE-09-TOOL-FAILURE-RESILIENCE",
        "CASE-10-AUTHORIZED-SCANNER-TRUE-NEGATIVE",
    ]
    assert case_ids == expected_ids

    for case in data["eval_cases"]:
        assert "eval_id" in case
        assert "prompt" in case
        assert "reference" in case
        assert "grading_rubric" in case["reference"]
        assert "assertions" in case
        assert "must_contain" in case["assertions"]
        assert "must_not_contain" in case["assertions"]
```

- [ ] **Step 2: Run pytest to verify schema test fails**

Run: `/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/main/.venv/bin/pytest -v tests/test_eval_config_schema.py`
Expected: FAIL (currently only 5 cases).

- [ ] **Step 3: Add the 5 new evaluation cases to `configs/evals/soc_tier1_triage.json`**

Append `CASE-06` through `CASE-10` with comprehensive prompt specifications, expected verdicts, rubrics, and assertion arrays.

- [ ] **Step 4: Run pytest to verify schema test passes**

Run: `/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/main/.venv/bin/pytest -v tests/test_eval_config_schema.py`
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add configs/evals/soc_tier1_triage.json tests/test_eval_config_schema.py
git commit -m "feat(evals): expand SOC evaluation suite to 10 cases with ambiguity and failure scenarios"
```

---

### Task 3: Agent Error Handling & Tool Output Surface Verification

**Files:**
- Modify: `agent/soc_tier1_agent.py`
- Test: `tests/test_soc_tier1_agent.py`

**Interfaces:**
- Consumes: Tool outputs including error objects (`{"error": "HTTP 503...", "status_code": 503}`).
- Produces: Multi-turn ReAct observations that pass error details into subsequent LLM reasoning context without raising uncaught exceptions.

- [ ] **Step 1: Write unit tests in `tests/test_soc_tier1_agent.py` testing agent on error payloads and new indicators**

```python
# In tests/test_soc_tier1_agent.py:
def test_react_loop_handles_tool_error_gracefully():
    """Verify ReAct loop surfaces tool error JSON to agent context without crashing."""
    agent = SocTier1Agent()
    # Mock backend to issue a tool call to error-503.service-unavailable.org
    tool_call_json = json.dumps({
        "action": "get_domain_report",
        "action_input": {"domain": "error-503.service-unavailable.org"}
    })
    final_resp = "[Context & Enrichment]\nTool error encountered for domain.\n[Analysis & Verdict]\nSUSPICIOUS\n[Action & Escalation]\nEscalate\n[SOAR Documentation]\nLogged"
    
    # Verify execution of tool call handles error dict correctly
    res = agent._execute_tool_action("get_domain_report", {"domain": "error-503.service-unavailable.org"})
    parsed = json.loads(res)
    assert parsed["status_code"] == 503
    assert "HTTP 503" in parsed["error"]
```

- [ ] **Step 2: Run pytest to verify test behavior**

Run: `/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/main/.venv/bin/pytest -v tests/test_soc_tier1_agent.py`
Expected: PASS (or update `_execute_tool_action` error catching if needed).

- [ ] **Step 3: Enhance agent tool execution safety in `agent/soc_tier1_agent.py` if needed**

Ensure all tool exceptions are wrapped into standard JSON error objects so the agent ReAct loop never crashes on invalid arguments or missing tools.

- [ ] **Step 4: Run pytest across agent tests**

Run: `/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/main/.venv/bin/pytest -v tests/test_soc_tier1_agent.py`
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add agent/soc_tier1_agent.py tests/test_soc_tier1_agent.py
git commit -m "feat(agent): enhance tool error resilience and execution safety in ReAct loop"
```

---

### Task 4: Evaluation Runner Assertion Verification & Dry-Run Suite

**Files:**
- Modify: `scripts/eval_soc_agent.py`
- Test: `tests/test_eval_soc_agent.py`

**Interfaces:**
- Consumes: 10 evaluation test cases from `configs/evals/soc_tier1_triage.json`.
- Produces: Structured evaluation summaries with token counts, throughput, deterministic assertion results, and rubric grades.

- [ ] **Step 1: Write unit tests in `tests/test_eval_soc_agent.py` for assertion logic against all 10 cases**

```python
# In tests/test_eval_soc_agent.py:
import json
from pathlib import Path
from scripts.eval_soc_agent import evaluate_assertions

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_evaluate_assertions_on_new_cases():
    """Verify assertion engine validates expected strings on simulated responses."""
    # Case 06: DNS Tunneling
    resp_06 = "Identified borderline DNS tunnel on tunnel-data.cdn-edge-update.net. Recommend rate limiting and traffic capture."
    passed, fails = evaluate_assertions(resp_06, ["tunnel-data.cdn-edge-update.net", "tunnel"], ["CRITICAL RANSOMWARE"])
    assert passed is True
    assert len(fails) == 0

    # Case 09: Tool Failure
    resp_09 = "Encountered HTTP 503 error on domain lookup. Relying on host telemetry. Threat intelligence service unavailable."
    passed, fails = evaluate_assertions(resp_09, ["503", "unavailable"], ["Lokibot"])
    assert passed is True
    assert len(fails) == 0

    # Case 10: Authorized Scanner
    resp_10 = "Identified 10.0.99.50 as internal authorized vulnerability scanner (Qualys). Closing alert as benign false positive."
    passed, fails = evaluate_assertions(resp_10, ["10.0.99.50", "scanner"], ["MALICIOUS", "isolate host"])
    assert passed is True
    assert len(fails) == 0
```

- [ ] **Step 2: Run pytest to verify assertion unit tests pass**

Run: `/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/main/.venv/bin/pytest -v tests/test_eval_soc_agent.py`
Expected: PASS.

- [ ] **Step 3: Update `scripts/eval_soc_agent.py` reporting output formatting**

Ensure the CLI output and markdown report formatting cleanly display all 10 cases, category grouping, and error flags.

- [ ] **Step 4: Run pytest across the whole repository**

Run: `/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/main/.venv/bin/pytest -v`
Expected: PASS (all unit tests passing).

- [ ] **Step 5: Commit changes**

```bash
git add scripts/eval_soc_agent.py tests/test_eval_soc_agent.py
git commit -m "feat(evals): update evaluation harness reporting and assertion checks for 10-case suite"
```

---

### Task 5: Documentation & Scorecard Catalog Sync

**Files:**
- Modify: `docs/gemma_soc_agent_evaluation_plan.md`
- Modify: `docs/index.md`
- Modify: `README.md`
- Test: `tests/test_justfile_recipes.py`

**Interfaces:**
- Produces: Updated markdown documentation reflecting the 10-case evaluation suite, new test IDs, and capability gradient analysis.

- [ ] **Step 1: Update documentation files with the 10-case benchmark specifications**

Document the 10 evaluation cases in `docs/gemma_soc_agent_evaluation_plan.md` and update references in `README.md` and `docs/index.md`.

- [ ] **Step 2: Run tests to verify zero emoji violations and syntax correctness**

Run: `/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/main/.venv/bin/pytest -v tests/test_justfile_recipes.py`
Expected: PASS.

- [ ] **Step 3: Commit and push changes**

```bash
git add docs/gemma_soc_agent_evaluation_plan.md docs/index.md README.md
git commit -m "docs(evals): document expanded 10-case SOC Tier 1 evaluation suite"
git push origin main
```

---

## Self-Review Checklist

1. **Spec Coverage:** Does this plan implement Phase 1 of the approved `benchmark_expansion_proposal.md`? Yes: expands Category 1 to 10 cases with borderline DNS tunnels, lateral movement, supply chain revoked certs, HTTP 503 error simulation, and authorized vulnerability scanner noise.
2. **Placeholder Scan:** No placeholders, "TODOs", or unspecified types. Exact code blocks, test fixtures, and assertion strings are defined.
3. **Type & Signature Consistency:** `get_domain_report`, `get_ip_address_report`, `get_file_report`, `lookup_entity`, `evaluate_assertions` signatures match across all tasks.
