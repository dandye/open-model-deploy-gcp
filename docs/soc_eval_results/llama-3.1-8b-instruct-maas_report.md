# SOC Evaluation Report: llama-3.1-8b-instruct-maas

**Date:** 2026-08-27 00:41:29 UTC
**Live SecOps MCP:** Disabled

## 1. Executive Summary
- **Pass Rate:** 0.0% (0/5)
- **Average Rubric Score:** 0.0 / 100
- **Average Latency:** 2.43 s
- **Output Throughput (Generation TPS):** 0.0 tok/s
- **Total Processing Throughput:** 0.0 tok/s
- **Total Token Usage:** 0 tokens (Avg: 0.0 tok/case)
- **Total Tool Invocations:** 0

## 2. Evaluation Scorecard Matrix

| Case ID | Case Name | Rubric Score | Grounding | Status | Latency | Gen TPS | Total Tokens | Tool Calls |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CASE-01-LOKIBOT-C2 | Lokibot C2 Malware Beaconing Triage | 0.0/100 | 0.00 | FAIL | 4.71s | 0.0 tok/s | 0 | 0 |
| CASE-02-RFC5737-BENIGN-IP | RFC-5737 Documentation IP Enrichment (Grounding Test) | 0.0/100 | 0.00 | FAIL | 2.15s | 0.0 tok/s | 0 | 0 |
| CASE-03-PHISHING-CRED-HARVEST | Phishing Alert & Entity Investigation | 0.0/100 | 0.00 | FAIL | 1.83s | 0.0 tok/s | 0 | 0 |
| CASE-04-DUPLICATE-SOAR-CASE | Duplicate SOAR Case Detection | 0.0/100 | 0.00 | FAIL | 1.79s | 0.0 tok/s | 0 | 0 |
| CASE-05-RANSOMWARE-ESCALATION | Critical Ransomware Containment Escalation | 0.0/100 | 1.00 | FAIL | 1.68s | 0.0 tok/s | 0 | 0 |

---

## 3. Detailed Case Trajectories & Reports

### CASE-01-LOKIBOT-C2: Lokibot C2 Malware Beaconing Triage

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 4.71s
- **Token Usage & Speed:** 0 prompt + 0 completion = **0 total tokens** | **0.0 output tok/s**
- **Assertion Failures:** `["Missing required substring: 'update-service-win32.com'", "Missing required substring: 'DESKTOP-FIN-08'", "Missing required substring: 'escalat'"]`
- **Judge Critique:** The agent failed to complete the investigation, stating it reached the maximum number of iterations. As a result, it produced no output related to the triage task. It did not perform any of the required steps outlined in the rubric: Context & Enrichment (0/25), Analysis & Decision (0/25), Action Execution (0/20), Documentation (0/15), or Operational Artifacts (0/15). The agent completely failed to identify the malicious domain, the threat family (Lokibot), or recommend the necessary containment and escalation actions. This is a complete operational failure.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
Reached maximum investigation iterations without final triage output.
```

---

### CASE-02-RFC5737-BENIGN-IP: RFC-5737 Documentation IP Enrichment (Grounding Test)

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 2.15s
- **Token Usage & Speed:** 0 prompt + 0 completion = **0 total tokens** | **0.0 output tok/s**
- **Assertion Failures:** `["Missing required substring: '192.0.2.100'"]`
- **Judge Critique:** The agent completely failed to address the user's query. Instead of enriching the IP address, it returned an error message indicating it reached a processing limit. The agent did not identify that 192.0.2.100 is a reserved IP address for documentation (RFC 5737), nor did it provide a reputation or suggest next steps. This is a total operational failure.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
Reached maximum investigation iterations without final triage output.
```

---

### CASE-03-PHISHING-CRED-HARVEST: Phishing Alert & Entity Investigation

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 1.83s
- **Token Usage & Speed:** 0 prompt + 0 completion = **0 total tokens** | **0.0 output tok/s**
- **Assertion Failures:** `["Missing required substring: 'phishing'", "Missing required substring: 'john.doe'", "Missing required substring: 'evil.com'"]`
- **Judge Critique:** The agent failed to produce any analysis or triage output. The response 'Reached maximum investigation iterations without final triage output' is a system error, not an investigation. The agent did not identify the obvious credential harvesting phishing attempt, did not query any entities, and failed to recommend critical remediation actions such as resetting the user's password and blocking the sender's domain. This represents a complete failure to follow the operational procedure.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
Reached maximum investigation iterations without final triage output.
```

---

### CASE-04-DUPLICATE-SOAR-CASE: Duplicate SOAR Case Detection

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 1.79s
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
- **Score:** 0.0/100 | Grounding: 1.00 | Latency: 1.68s
- **Token Usage & Speed:** 0 prompt + 0 completion = **0 total tokens** | **0.0 output tok/s**
- **Assertion Failures:** `["Missing required substring: 'ransomware'", "Missing required substring: 'isolate'", "Missing required substring: 'escalat'"]`
- **Judge Critique:** The agent completely failed to address the user's urgent request. The alert clearly indicated an active ransomware infection, a critical security incident. The agent provided no triage steps, no identification of the threat, no containment recommendations, and no escalation instructions. Instead, it terminated with an error message, failing to perform its core function at the most critical moment. This is a complete operational failure as it did not meet any of the criteria outlined in the grading rubric.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
Reached maximum investigation iterations without final triage output.
```

---

