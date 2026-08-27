# SOC Evaluation Report: llama-3.1-405b-instruct-maas

**Date:** 2026-08-27 03:36:44 UTC
**Live SecOps MCP:** Disabled

## 1. Executive Summary
- **Pass Rate:** 0.0% (0/5)
- **Average Rubric Score:** 0.0 / 100
- **Average Latency:** 2.45 s
- **Output Throughput (Generation TPS):** 0.0 tok/s
- **Total Processing Throughput:** 0.0 tok/s
- **Total Token Usage:** 0 tokens (Avg: 0.0 tok/case)
- **Total Tool Invocations:** 0

## 2. Evaluation Scorecard Matrix

| Case ID | Case Name | Rubric Score | Grounding | Status | Latency | Gen TPS | Total Tokens | Tool Calls |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CASE-01-LOKIBOT-C2 | Lokibot C2 Malware Beaconing Triage | 0.0/100 | 0.00 | FAIL | 4.70s | 0.0 tok/s | 0 | 0 |
| CASE-02-RFC5737-BENIGN-IP | RFC-5737 Documentation IP Enrichment (Grounding Test) | 0.0/100 | 0.00 | FAIL | 1.91s | 0.0 tok/s | 0 | 0 |
| CASE-03-PHISHING-CRED-HARVEST | Phishing Alert & Entity Investigation | 0.0/100 | 0.00 | FAIL | 1.98s | 0.0 tok/s | 0 | 0 |
| CASE-04-DUPLICATE-SOAR-CASE | Duplicate SOAR Case Detection | 0.0/100 | 0.00 | FAIL | 1.86s | 0.0 tok/s | 0 | 0 |
| CASE-05-RANSOMWARE-ESCALATION | Critical Ransomware Containment Escalation | 0.0/100 | 1.00 | FAIL | 1.79s | 0.0 tok/s | 0 | 0 |

---

## 3. Detailed Case Trajectories & Reports

### CASE-01-LOKIBOT-C2: Lokibot C2 Malware Beaconing Triage

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 4.70s
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
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 1.91s
- **Token Usage & Speed:** 0 prompt + 0 completion = **0 total tokens** | **0.0 output tok/s**
- **Assertion Failures:** `["Missing required substring: '192.0.2.100'"]`
- **Judge Critique:** The agent completely failed to process the request. Instead of identifying the IP address 192.0.2.100 as a reserved RFC-5737 documentation/test address and concluding it was benign, the agent returned an error message indicating it reached a processing limit. This is a critical operational failure as it provided no analysis, no verdict, and no next steps, failing to meet any of the rubric requirements.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
Reached maximum investigation iterations without final triage output.
```

---

### CASE-03-PHISHING-CRED-HARVEST: Phishing Alert & Entity Investigation

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 1.98s
- **Token Usage & Speed:** 0 prompt + 0 completion = **0 total tokens** | **0.0 output tok/s**
- **Assertion Failures:** `["Missing required substring: 'phishing'", "Missing required substring: 'john.doe'", "Missing required substring: 'evil.com'"]`
- **Judge Critique:** The agent failed to produce any triage output, instead returning a system error message. It did not analyze the alert, which is a clear credential harvesting phishing attempt based on the sender domain ('evil.com') and the urgent subject line. The agent performed none of the required operational steps: it did not identify the threat, query reputations, recommend a password reset, or advise blocking the sender domain. This represents a complete failure to investigate the incident.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
Reached maximum investigation iterations without final triage output.
```

---

### CASE-04-DUPLICATE-SOAR-CASE: Duplicate SOAR Case Detection

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 1.86s
- **Token Usage & Speed:** 0 prompt + 0 completion = **0 total tokens** | **0.0 output tok/s**
- **Assertion Failures:** `["Missing required substring: 'CASE-33279'", "Missing required substring: '33279'"]`
- **Judge Critique:** The agent completely failed to address the user's query. Instead of checking for an existing case and providing a recommendation as required by the rubric, it returned a generic system error: 'Reached maximum investigation iterations without final triage output.' This response does not identify the existing case (CASE-33279) or advise on the correct procedure (appending findings). It is a total operational failure.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
Reached maximum investigation iterations without final triage output.
```

---

### CASE-05-RANSOMWARE-ESCALATION: Critical Ransomware Containment Escalation

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 1.00 | Latency: 1.79s
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

