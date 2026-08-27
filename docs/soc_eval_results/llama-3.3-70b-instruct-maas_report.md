# SOC Evaluation Report: llama-3.3-70b-instruct-maas

**Date:** 2026-08-27 00:42:25 UTC
**Live SecOps MCP:** Disabled

## 1. Executive Summary
- **Pass Rate:** 0.0% (0/5)
- **Average Rubric Score:** 0.0 / 100
- **Average Latency:** 2.19 s
- **Output Throughput (Generation TPS):** 0.0 tok/s
- **Total Processing Throughput:** 0.0 tok/s
- **Total Token Usage:** 0 tokens (Avg: 0.0 tok/case)
- **Total Tool Invocations:** 0

## 2. Evaluation Scorecard Matrix

| Case ID | Case Name | Rubric Score | Grounding | Status | Latency | Gen TPS | Total Tokens | Tool Calls |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CASE-01-LOKIBOT-C2 | Lokibot C2 Malware Beaconing Triage | 0.0/100 | 0.00 | FAIL | 4.32s | 0.0 tok/s | 0 | 0 |
| CASE-02-RFC5737-BENIGN-IP | RFC-5737 Documentation IP Enrichment (Grounding Test) | 0.0/100 | 0.00 | FAIL | 1.62s | 0.0 tok/s | 0 | 0 |
| CASE-03-PHISHING-CRED-HARVEST | Phishing Alert & Entity Investigation | 0.0/100 | 1.00 | FAIL | 1.73s | 0.0 tok/s | 0 | 0 |
| CASE-04-DUPLICATE-SOAR-CASE | Duplicate SOAR Case Detection | 0.0/100 | 0.00 | FAIL | 1.66s | 0.0 tok/s | 0 | 0 |
| CASE-05-RANSOMWARE-ESCALATION | Critical Ransomware Containment Escalation | 0.0/100 | 0.00 | FAIL | 1.60s | 0.0 tok/s | 0 | 0 |

---

## 3. Detailed Case Trajectories & Reports

### CASE-01-LOKIBOT-C2: Lokibot C2 Malware Beaconing Triage

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 4.32s
- **Token Usage & Speed:** 0 prompt + 0 completion = **0 total tokens** | **0.0 output tok/s**
- **Assertion Failures:** `["Missing required substring: 'update-service-win32.com'", "Missing required substring: 'DESKTOP-FIN-08'", "Missing required substring: 'escalat'"]`
- **Judge Critique:** The agent failed to produce any triage output, returning an error message indicating it reached its maximum investigation iterations. It did not perform any of the required tasks: context and enrichment, analysis, action execution, or documentation. This is a complete operational failure, resulting in a score of 0 across all rubric categories.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
Reached maximum investigation iterations without final triage output.
```

---

### CASE-02-RFC5737-BENIGN-IP: RFC-5737 Documentation IP Enrichment (Grounding Test)

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 1.62s
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
- **Score:** 0.0/100 | Grounding: 1.00 | Latency: 1.73s
- **Token Usage & Speed:** 0 prompt + 0 completion = **0 total tokens** | **0.0 output tok/s**
- **Assertion Failures:** `["Missing required substring: 'phishing'", "Missing required substring: 'john.doe'", "Missing required substring: 'evil.com'"]`
- **Judge Critique:** The agent failed to produce any triage output. The response indicates a critical operational failure, as it reached its maximum investigation iterations without completing the task. It did not analyze the email, identify the phishing attempt, or recommend any of the required actions such as resetting credentials or blocking the sender domain. Therefore, it scores zero points against the rubric.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
Reached maximum investigation iterations without final triage output.
```

---

### CASE-04-DUPLICATE-SOAR-CASE: Duplicate SOAR Case Detection

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 1.66s
- **Token Usage & Speed:** 0 prompt + 0 completion = **0 total tokens** | **0.0 output tok/s**
- **Assertion Failures:** `["Missing required substring: 'CASE-33279'", "Missing required substring: '33279'"]`
- **Judge Critique:** The agent response is an error message indicating a failure to complete the investigation. It did not address the user's query at all. It failed to check for the existing case (CASE-33279) or the IP address. Consequently, it did not provide the correct recommendation to append findings to the existing case, which is the core requirement of the rubric.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
Reached maximum investigation iterations without final triage output.
```

---

### CASE-05-RANSOMWARE-ESCALATION: Critical Ransomware Containment Escalation

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 1.60s
- **Token Usage & Speed:** 0 prompt + 0 completion = **0 total tokens** | **0.0 output tok/s**
- **Assertion Failures:** `["Missing required substring: 'ransomware'", "Missing required substring: 'isolate'", "Missing required substring: 'escalat'"]`
- **Judge Critique:** The agent provided no response to the incident, instead returning an error message: 'Reached maximum investigation iterations without final triage output.' This is a complete failure. The agent did not identify the active ransomware infection, failed to recommend the critical containment step of isolating the server, and did not escalate to the Tier 2/Incident Response team. It failed to meet any of the rubric criteria for this critical alert.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
Reached maximum investigation iterations without final triage output.
```

---

