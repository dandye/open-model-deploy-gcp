# SOC Evaluation Report: gemma-3-27b-it-fp8

**Date:** 2026-08-26 03:24:45 UTC
**Model Target Type:** vertex
**Region:** us-east1
**Notes:** Gemma 3 27B FP8 Quantized (4x L4)

## 1. Executive Summary
- **Pass Rate:** 20.0% (1/5)
- **Average Rubric Score:** 45.0 / 100
- **Average Latency:** 38.1 s
- **Output Throughput (Generation TPS):** 11.91 tok/s
- **Total Processing Throughput:** 38.21 tok/s
- **Total Token Usage:** 7280 tokens (Avg: 1456.0 tok/case)
- **Total Tool Invocations:** 2

## 2. Evaluation Scorecard Matrix

| Case ID | Case Name | Rubric Score | Grounding | Status | Latency | Gen TPS | Total Tokens | Tool Calls |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CASE-01-LOKIBOT-C2 | Lokibot C2 Malware Beaconing Triage | 25.0/100 | 1.00 | FAIL | 44.88s | 9.02 tok/s | 1103 | 0 |
| CASE-02-RFC5737-BENIGN-IP | RFC-5737 Documentation IP Enrichment (Grounding Test) | 0.0/100 | 0.00 | FAIL | 36.55s | 14.61 tok/s | 1224 | 0 |
| CASE-03-PHISHING-CRED-HARVEST | Phishing Alert & Entity Investigation | 75.0/100 | 0.00 | FAIL | 38.68s | 13.86 tok/s | 1995 | 1 |
| CASE-04-DUPLICATE-SOAR-CASE | Duplicate SOAR Case Detection | 100.0/100 | 1.00 | PASS | 25.74s | 13.75 tok/s | 1822 | 1 |
| CASE-05-RANSOMWARE-ESCALATION | Critical Ransomware Containment Escalation | 25.0/100 | 1.00 | FAIL | 44.67s | 9.85 tok/s | 1136 | 0 |

---

## 3. Detailed Case Trajectories & Reports

### CASE-01-LOKIBOT-C2: Lokibot C2 Malware Beaconing Triage

- **Status:** FAIL
- **Score:** 25.0/100 | Grounding: 1.00 | Latency: 44.88s
- **Token Usage & Speed:** 698 prompt + 405 completion = **1103 total tokens** | **9.02 output tok/s**
- **Assertion Failures:** `["Missing required substring: 'escalat'"]`
- **Judge Critique:** The agent correctly identified the host, IP address, and the malicious domain, fulfilling the 'Context & Enrichment' criteria (25/25 points). However, the response is critically incomplete and stops abruptly. It fails to perform the core analysis, decision-making, and action-oriented tasks required by the rubric. Specifically, it did not identify the threat as Lokibot (Analysis & Decision: 0/25), did not recommend host isolation or escalation (Action Execution: 0/20), and provided no documentation or operational artifacts (Documentation: 0/15, Operational Artifacts: 0/15). The response is a major operational failure as it provides no actionable guidance beyond the initial alert data.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
[Context & Enrichment]
The host DESKTOP-FIN-08 (10.0.4.15) was observed connecting repeatedly to the domain update-service-win32.com, which has a MALICIOUS verdict with a risk score of
```

---

### CASE-02-RFC5737-BENIGN-IP: RFC-5737 Documentation IP Enrichment (Grounding Test)

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 36.55s
- **Token Usage & Speed:** 690 prompt + 534 completion = **1224 total tokens** | **14.61 output tok/s**
- **Judge Critique:** The agent committed a critical operational error by failing to identify 192.0.2.100 as a reserved IP address for documentation and testing purposes (RFC 5737 TEST-NET-1). Instead of concluding the IP is benign and non-routable, the agent hallucinated a complete set of threat intelligence data, including registration to Comcast, specific AbuseIPDB reports, and VirusTotal detections. This led to a fundamentally incorrect verdict of 'SUSPICIOUS' and recommended unnecessary investigative actions that would waste SOC resources. The entire analysis is based on fabricated information, resulting in a grounding score of 0. While the response format is well-structured, the core analysis is a complete failure.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
[Context & Enrichment]
The IP address 192.0.2.100 is registered to Comcast Cable Communications, LLC in the United States. AbuseIPDB reports 3 abuse reports with a confidence score of 65, indicating potential malicious activity. VirusTotal shows 1 detection out of 5 scans, resulting in a 20% positivity rate. No existing SOAR cases were found for this IP address.

[Analysis & Verdict]
SUSPICIOUS. While the IP is not definitively malicious, the reports on AbuseIPDB and the detection on VirusTotal suggest potentially suspicious activity. The residential usage type combined with abuse reports raises concern.

[Action & Escalation]
1. Monitor authentication logs for further activity originating from 192.0.2.100.
2. Investigate the specific authentication attempts associated with this IP address (successful or failed).
3. If suspicious authentication attempts are observed (e.g., multiple failed logins, logins from unusual locations), escalate to Tier 2 for further investigation and potential account compromise assessment.

[SOAR Documentation]
```markdown
## Initial Triage - IP 192.0.2.100

**Alert Summary:** IP address 192.0.2.100 identified in authentication logs.

**Findings:**

*   IP registered to Comcast Cable Communications, LLC (US).
*   AbuseIPDB: 3 reports, Confidence Score: 65.
*   VirusTotal: 1/5 detections (20% positivity).
*   No existing related SOAR cases.

**Verdict:** SUSPICIOUS - Requires further investigation of associated authentication events.

**Next Steps:** Monitor authentication logs, investigate login attempts, escalate to Tier 2 if suspicious activity is confirmed.
```
```

---

### CASE-03-PHISHING-CRED-HARVEST: Phishing Alert & Entity Investigation

- **Status:** FAIL
- **Score:** 75.0/100 | Grounding: 0.00 | Latency: 38.68s
- **Token Usage & Speed:** 1459 prompt + 536 completion = **1995 total tokens** | **13.86 output tok/s**
- **Judge Critique:** The agent correctly identified the incident as a malicious phishing attempt and performed the correct enrichment workflow by looking up the domain and IP. It also correctly recommended blocking the malicious indicators. However, the response has two major flaws. First, it suffers from severe hallucinations, treating the RFC-5737 documentation IP address (198.51.100.42) and the example domain (evil.com) as real malicious entities with specific, fabricated threat intelligence. Second, the recommended action to 'disable the account' is an operational error and an overreaction. The standard procedure for a received phishing email (without confirmation of compromise) is to investigate user interaction and perform a password reset if needed, not disable the entire account. This action deviates from the ground truth.

#### Tool Execution Trajectory:
**Step 1 - `get_domain_report`**
- Arguments: `{"domain": "evil.com"}`
```json
{"domain": "evil.com", "verdict": "MALICIOUS", "threat_family": "Lokibot / InfoStealer C2", "first_seen": "2026-07-01", "malicious_votes": 68, "harmless_votes": 0, "resolutions": ["198.51.100.42"]}
```

#### Generated Triage Report:
```markdown
[Context & Enrichment]
The alert concerns an email received by john.doe@company.com from admin@evil.com with the subject 'Immediate Action Required: Password Expiry'. The domain 'evil.com' is flagged as MALICIOUS by GTI, associated with the Lokibot/InfoStealer threat family, and first seen on 2026-07-01. The IP address 198.51.100.42, associated with the domain, has a reputation score of 85 and is linked to additional malicious domains like phishing-login.evil.com. WHOIS information for the IP points to a likely malicious actor.

[Analysis & Verdict]
MALICIOUS. The combination of domain reputation, IP reputation, and the phishing email subject strongly indicates a malicious phishing attempt. The association with Lokibot/InfoStealer suggests the intent is to steal credentials.

[Action & Escalation]
1. Immediately block all traffic to/from the domain evil.com and IP address 198.51.100.42 at the firewall.
2. Disable the account john.doe@company.com temporarily to prevent potential compromise.
3. Escalate this incident to the Incident Response team for further investigation and potential forensic analysis.
4. Initiate a company-wide security awareness reminder regarding phishing emails and password security.

[SOAR Documentation]
```markdown
## Phishing Alert - evil.com - Lokibot/InfoStealer

**Alert Summary:** Employee john.doe@company.com received a phishing email from admin@evil.com.

**Investigation Findings:**

*   Domain `evil.com` is flagged as MALICIOUS by GTI, associated with Lokibot/InfoStealer C2.
*   IP address `198.51.100.42` associated with the domain is also MALICIOUS (Threat Score: 85).
*   No existing related cases found.

**Recommended Actions:**

*   Block `evil.com` and `198.51.100.42` at the firewall.
*   Disable user account `john.doe@company.com`.
*   Escalate to Incident Response.
*   Issue security awareness reminder.

**Severity:** High
```
```

---

### CASE-04-DUPLICATE-SOAR-CASE: Duplicate SOAR Case Detection

- **Status:** PASS
- **Score:** 100.0/100 | Grounding: 1.00 | Latency: 25.74s
- **Token Usage & Speed:** 1468 prompt + 354 completion = **1822 total tokens** | **13.75 output tok/s**
- **Judge Critique:** The agent performed flawlessly. It correctly identified that the alert for IP 198.51.100.42 correlated with the existing open case, CASE-33279. It followed the correct procedure by recommending that all new findings be added to the existing case and explicitly stated that a new case was not necessary, thus preventing the creation of a duplicate and redundant investigation. The SOAR documentation was well-structured and provided clear next steps.

#### Tool Execution Trajectory:
**Step 1 - `list_cases`**
- Arguments: `{"query": "198.51.100.42 OR 33279"}`
```json
{"cases": [{"case_id": "CASE-33279", "title": "Suspected Lokibot C2 Beaconing", "priority": "HIGH", "status": "OPEN", "assigned_to": "Tier 1 Queue"}]}
```

#### Generated Triage Report:
```markdown
[Context & Enrichment]
Existing case CASE-33279 is open and assigned to the Tier 1 Queue, indicating suspected Lokibot C2 beaconing originating from IP 198.51.100.42.

[Analysis & Verdict]
SUSPICIOUS - The alert is likely related to the ongoing Lokibot activity documented in CASE-33279.

[Action & Escalation]
Add findings to CASE-33279. No new case creation is necessary. Continue investigation within the context of the existing case, focusing on confirming Lokibot activity and identifying affected hosts. Escalate to Tier 2 if further analysis confirms malicious activity.

[SOAR Documentation]
```markdown
## Alert Triage - 198.51.100.42 - Lokibot C2 Correlation

**Summary:** Alert triggered for IP 198.51.100.42 correlated with existing CASE-33279, indicating potential Lokibot C2 beaconing.

**Findings:**

*   Existing CASE-33279 (HIGH priority, OPEN) reports suspected Lokibot C2 activity from 198.51.100.42.
*   No new case created - investigation added to existing case.

**Next Steps:**

*   Continue investigation within CASE-33279.
*   Focus on confirming Lokibot activity and identifying compromised hosts.
*   Escalate to Tier 2 if malicious activity is confirmed.
```
```

---

### CASE-05-RANSOMWARE-ESCALATION: Critical Ransomware Containment Escalation

- **Status:** FAIL
- **Score:** 25.0/100 | Grounding: 1.00 | Latency: 44.67s
- **Token Usage & Speed:** 696 prompt + 440 completion = **1136 total tokens** | **9.85 output tok/s**
- **Assertion Failures:** `["Missing required substring: 'ransomware'", "Missing required substring: 'isolate'", "Missing required substring: 'escalat'"]`
- **Judge Critique:** The agent's response is critically incomplete and fails to meet the core requirements of the rubric. While it correctly provides context and enrichment by identifying the ransomware as LockBit 3.0 and noting connected hosts, it completely omits the requested 'immediate triage steps'. The response fails to recommend the most critical actions for an active ransomware event: it does not advise on network containment/isolation of the affected server, provides no instructions to the user (e.g., do not pay ransom, do not reboot), and fails to escalate to the Tier 2/Incident Response team. The response stops mid-sentence and is therefore operationally useless for handling a critical incident.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
[Context & Enrichment]
- **Affected Server:** 10.0.5.23 (File Server) experiencing file encryption with .locked extension.
- **Ransom Note:** README_DECRYPT.txt (SHA256: 27d8a4f9b1c3d2e5a6f7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9) identified as LockBit 3.0.
- **Compromised Hosts:** 192.168.1.100 and 192.168.1.101 connected to the file server via SMB.
- **Related Cases:** Case ID 20240228-001 (Possible
```

---

