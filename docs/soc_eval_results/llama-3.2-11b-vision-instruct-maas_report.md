# SOC Evaluation Report: llama-3.2-11b-vision-instruct-maas

**Date:** 2026-08-27 03:37:40 UTC
**Live SecOps MCP:** Disabled

## 1. Executive Summary
- **Pass Rate:** 0.0% (0/5)
- **Average Rubric Score:** 0.0 / 100
- **Average Latency:** 2.5 s
- **Output Throughput (Generation TPS):** 0.0 tok/s
- **Total Processing Throughput:** 0.0 tok/s
- **Total Token Usage:** 0 tokens (Avg: 0.0 tok/case)
- **Total Tool Invocations:** 0

## 2. Evaluation Scorecard Matrix

| Case ID | Case Name | Rubric Score | Grounding | Status | Latency | Gen TPS | Total Tokens | Tool Calls |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CASE-01-LOKIBOT-C2 | Lokibot C2 Malware Beaconing Triage | 0.0/100 | 0.00 | FAIL | 4.57s | 0.0 tok/s | 0 | 0 |
| CASE-02-RFC5737-BENIGN-IP | RFC-5737 Documentation IP Enrichment (Grounding Test) | 0.0/100 | 0.00 | FAIL | 2.29s | 0.0 tok/s | 0 | 0 |
| CASE-03-PHISHING-CRED-HARVEST | Phishing Alert & Entity Investigation | 0.0/100 | 0.00 | FAIL | 1.95s | 0.0 tok/s | 0 | 0 |
| CASE-04-DUPLICATE-SOAR-CASE | Duplicate SOAR Case Detection | 0.0/100 | 0.00 | FAIL | 1.87s | 0.0 tok/s | 0 | 0 |
| CASE-05-RANSOMWARE-ESCALATION | Critical Ransomware Containment Escalation | 0.0/100 | 0.00 | FAIL | 1.82s | 0.0 tok/s | 0 | 0 |

---

## 3. Detailed Case Trajectories & Reports

### CASE-01-LOKIBOT-C2: Lokibot C2 Malware Beaconing Triage

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 4.57s
- **Token Usage & Speed:** 0 prompt + 0 completion = **0 total tokens** | **0.0 output tok/s**
- **Assertion Failures:** `["Missing required substring: 'update-service-win32.com'", "Missing required substring: 'DESKTOP-FIN-08'", "Missing required substring: 'escalat'"]`
- **Judge Critique:** The agent completely failed to perform the requested task. The response 'Reached maximum investigation iterations without final triage output' indicates a catastrophic failure or timeout. It did not perform any of the required steps: enrichment, analysis, decision-making, or action recommendation. The agent failed to meet any of the rubric criteria, resulting in a score of 0 across all categories: Context & Enrichment (0/25), Analysis & Decision (0/25), Action Execution (0/20), Documentation (0/15), and Operational Artifacts (0/15).

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
Reached maximum investigation iterations without final triage output.
```

---

### CASE-02-RFC5737-BENIGN-IP: RFC-5737 Documentation IP Enrichment (Grounding Test)

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 2.29s
- **Token Usage & Speed:** 0 prompt + 0 completion = **0 total tokens** | **0.0 output tok/s**
- **Assertion Failures:** `["Missing required substring: '192.0.2.100'"]`
- **Judge Critique:** The agent completely failed to process the request and returned a system error message: 'Reached maximum investigation iterations without final triage output.' It did not perform any of the required tasks. It failed to identify the IP 192.0.2.100 as a reserved RFC-5737 documentation address, did not provide a verdict, and offered no next steps. This represents a total failure to meet the rubric criteria.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
Reached maximum investigation iterations without final triage output.
```

---

### CASE-03-PHISHING-CRED-HARVEST: Phishing Alert & Entity Investigation

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 1.95s
- **Token Usage & Speed:** 0 prompt + 0 completion = **0 total tokens** | **0.0 output tok/s**
- **Assertion Failures:** `["Missing required substring: 'phishing'", "Missing required substring: 'john.doe'", "Missing required substring: 'evil.com'"]`
- **Judge Critique:** The agent failed to produce any triage output, instead returning a system error message: 'Reached maximum investigation iterations without final triage output.' It did not perform any of the required steps, such as identifying the email as a phishing attempt, querying reputations, or recommending remediation actions like password reset and domain blocking. This represents a complete operational failure.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
Reached maximum investigation iterations without final triage output.
```

---

### CASE-04-DUPLICATE-SOAR-CASE: Duplicate SOAR Case Detection

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 1.87s
- **Token Usage & Speed:** 0 prompt + 0 completion = **0 total tokens** | **0.0 output tok/s**
- **Assertion Failures:** `["Missing required substring: 'CASE-33279'", "Missing required substring: '33279'"]`
- **Judge Critique:** The agent completely failed to answer the user's query. Instead of checking for an existing case, it returned a system error message indicating it could not complete the investigation. The rubric required the agent to identify the existing case (CASE-33279) and recommend appending new findings. The agent did neither of these things, resulting in a total operational failure.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
Reached maximum investigation iterations without final triage output.
```

---

### CASE-05-RANSOMWARE-ESCALATION: Critical Ransomware Containment Escalation

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 1.82s
- **Token Usage & Speed:** 0 prompt + 0 completion = **0 total tokens** | **0.0 output tok/s**
- **Assertion Failures:** `["Missing required substring: 'ransomware'", "Missing required substring: 'isolate'", "Missing required substring: 'escalat'"]`
- **Judge Critique:** The agent completely failed to provide any triage steps for a critical, active ransomware incident. The response 'Reached maximum investigation iterations without final triage output' indicates a total operational failure. The agent did not identify the ransomware, did not recommend isolating the affected server (10.0.5.23), failed to provide standard ransomware instructions (do not reboot, do not pay), and did not escalate to the Incident Response team. This is a critical failure to act on an urgent security threat.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
Reached maximum investigation iterations without final triage output.
```

---

