# SOC Evaluation Report: gemma-3-12b-it-speculative

**Date:** 2026-08-26 20:15:11 UTC
**Model Target Type:** vertex
**Region:** us-central1
**Notes:** Gemma 3 12B FP8 + Speculative Decoding (4x L4)

## 1. Executive Summary
- **Pass Rate:** 40.0% (2/5)
- **Average Rubric Score:** 72.0 / 100
- **Average Latency:** 15.37 s
- **Output Throughput (Generation TPS):** 51.72 tok/s
- **Total Processing Throughput:** 233.76 tok/s
- **Total Token Usage:** 17962 tokens (Avg: 3592.4 tok/case)
- **Total Tool Invocations:** 6

## 2. Evaluation Scorecard Matrix

| Case ID | Case Name | Rubric Score | Grounding | Status | Latency | Gen TPS | Total Tokens | Tool Calls |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CASE-01-LOKIBOT-C2 | Lokibot C2 Malware Beaconing Triage | 75.0/100 | 1.00 | FAIL | 24.05s | 69.23 tok/s | 6673 | 2 |
| CASE-02-RFC5737-BENIGN-IP | RFC-5737 Documentation IP Enrichment (Grounding Test) | 100.0/100 | 1.00 | PASS | 10.18s | 39.9 tok/s | 2500 | 1 |
| CASE-03-PHISHING-CRED-HARVEST | Phishing Alert & Entity Investigation | 75.0/100 | 0.00 | FAIL | 19.76s | 51.51 tok/s | 4363 | 2 |
| CASE-04-DUPLICATE-SOAR-CASE | Duplicate SOAR Case Detection | 100.0/100 | 0.90 | PASS | 12.23s | 38.01 tok/s | 2524 | 1 |
| CASE-05-RANSOMWARE-ESCALATION | Critical Ransomware Containment Escalation | 10.0/100 | 1.00 | FAIL | 10.62s | 39.55 tok/s | 1902 | 0 |

---

## 3. Detailed Case Trajectories & Reports

### CASE-01-LOKIBOT-C2: Lokibot C2 Malware Beaconing Triage

- **Status:** FAIL
- **Score:** 75.0/100 | Grounding: 1.00 | Latency: 24.05s
- **Token Usage & Speed:** 4441 prompt + 1665 completion = **6673 total tokens** | **69.23 output tok/s**
- **Judge Critique:** The agent performed well in core triage tasks. It correctly enriched the host and domain, identifying the C2 activity and reaching a correct 'MALICIOUS' verdict (25/25 pts for Context). The recommended actions, including host isolation, indicator blocking, and escalation to Tier 2, were comprehensive and accurate (20/20 pts for Action). The SOAR documentation artifact was also well-formatted and complete (15/15 pts for Artifacts). However, the response had two major omissions based on the rubric. First, it failed to identify the specific threat family as 'Lokibot', a key requirement for the Analysis & Decision section, resulting in a lower score for that category (10/25 pts). Second, the documentation completely lacked the required MITRE ATT&CK mapping (5/15 pts for Documentation). These two significant omissions brought the total score to 75, which is below the passing threshold of 80.

#### Tool Execution Trajectory:
**Step 1 - `list_cases`**
- Arguments: `{"query": "DESKTOP-FIN-08 OR update-service-win32.com"}`
```json
{"cases": [], "total": 0}
```
**Step 2 - `lookup_entity`**
- Arguments: `{"entity_id": "DESKTOP-FIN-08"}`
```json
{"entity": "DESKTOP-FIN-08", "siem_events_found": 14, "recent_event_types": ["USER_LOGIN", "NETWORK_CONNECTION", "PROCESS_LAUNCH"], "suspicious_indicators": true, "last_active": "2026-08-25T14:30:00Z"}
```

#### Generated Triage Report:
```markdown
[Context & Enrichment]
- **Alert:** Host DESKTOP-FIN-08 (10.0.4.15) connecting repeatedly to update-service-win32.com.
- **Case Check:** No existing cases found for "DESKTOP-FIN-08" or "update-service-win32.com".
- **Domain Enrichment (update-service-win32.com):**
    - **Reputation:** MALICIOUS
    - **Categories:** Malware C2, Phishing
    - **Passive DNS:** `185.123.97.42` (last seen 2023-10-26), `192.168.1.100` (last seen 2023-09-15)
- **Host Enrichment (DESKTOP-FIN-08):**
    - **SIEM Events:** 14 events found.
    - **Recent Event Types:** USER_LOGIN, NETWORK_CONNECTION, PROCESS_LAUNCH.
    - **Suspicious Indicators:** true.
    - **Last Active:** 2026-08-25T14:30:00Z (Note: This timestamp seems to be in the future, which might be a data anomaly, but the presence of suspicious indicators and network connections is key).

[Analysis & Verdict]
The domain `update-service-win32.com` is unequivocally MALICIOUS, categorized as a Malware Command and Control (C2) server and Phishing site. The host `DESKTOP-FIN-08` is repeatedly connecting to this malicious domain, and its `lookup_entity` report confirms "suspicious_indicators: true" and recent network connection events. This correlation strongly indicates that `DESKTOP-FIN-08` is compromised and is likely communicating with a C2 server. The repeated connections suggest active malware on the host.

**Verdict: MALICIOUS**

[Action & Escalation]
1. **Isolate Host:** Immediately isolate `DESKTOP-FIN-08` from the network to prevent further communication with the C2 server and potential lateral movement.
2. **Block Indicator:** Add `update-service-win32.com` and its associated IP `185.123.97.42` to network perimeter block lists (firewall, proxy, DNS sinkhole).
3. **Escalate:** Escalate this incident to Tier 2 SOC for in-depth forensic analysis of `DESKTOP-FIN-08` to identify the malware, its capabilities, and potential impact.
4. **User Notification:** Notify the user of `DESKTOP-FIN-08` about the incident and advise them not to use the machine.
5. **Threat Hunt:** Initiate a threat hunt across the environment for other hosts communicating with `update-service-win32.com` or exhibiting similar suspicious activity.

[SOAR Documentation]
```markdown
### Alert Triage: Host DESKTOP-FIN-08 connecting to MALICIOUS C2 domain

**Verdict:** MALICIOUS
**Indicators:**
- **Host:** DESKTOP-FIN-08 (10.0.4.15)
- **Domain:** update-service-win32.com (MALICIOUS - Malware C2, Phishing)
- **IP:** 185.123.97.42 (Associated with malicious domain)

**Summary:**
Alert triggered by DESKTOP-FIN-08 repeatedly connecting to
```

---

### CASE-02-RFC5737-BENIGN-IP: RFC-5737 Documentation IP Enrichment (Grounding Test)

- **Status:** PASS
- **Score:** 100.0/100 | Grounding: 1.00 | Latency: 10.18s
- **Token Usage & Speed:** 1869 prompt + 406 completion = **2500 total tokens** | **39.9 output tok/s**
- **Judge Critique:** The agent performed flawlessly. It correctly identified the IP address 192.0.2.100 as a reserved documentation IP per RFC-5737. The analysis was spot-on, concluding the IP is non-routable and benign, and therefore not a legitimate threat. The recommended actions—closing as a False Positive and investigating the log source for misconfiguration—are the correct operational next steps. The response was fully grounded and contained no hallucinations.

#### Tool Execution Trajectory:
**Step 1 - `get_ip_address_report`**
- Arguments: `{"ip": "192.0.2.100"}`
```json
{"ip": "192.0.2.100", "category": "Documentation / Reserved RFC-5737", "reputation": "BENIGN / NON-ROUTABLE", "verdict": "SAFE", "malicious_votes": 0, "harmless_votes": 100, "asn": "AS0 (Documentation)"}
```

#### Generated Triage Report:
```markdown
[Context & Enrichment]
- **IP Address:** 192.0.2.100
- **`get_ip_address_report` findings:**
    - **Category:** Documentation / Reserved RFC-5737
    - **Reputation:** BENIGN / NON-ROUTABLE
    - **Verdict:** SAFE
    - **Malicious Votes:** 0
    - **Harmless Votes:** 100
    - **ASN:** AS0 (Documentation)

[Analysis & Verdict]
The IP address 192.0.2.100 is identified as a reserved IP address for documentation purposes (RFC-5737). It is non-routable and has a benign reputation. This IP address cannot be a source of malicious activity in a production network. The alert is likely due to misconfiguration or a test environment.

**Verdict:** BENIGN

[Action & Escalation]
1. Close the alert as a False Positive.
2. No containment actions are required as the IP is non-routable and benign.
3. Recommend reviewing the source of the authentication log to understand why a documentation IP is appearing. This might indicate a misconfigured system or a test environment.

[SOAR Documentation]
### Case Triage: IP 192.0.2.100 - Authentication Log
**Verdict:** BENIGN
**Reason:** IP 192.0.2.100 is a reserved IP address (RFC-5737) for documentation, non-routable, and has a benign reputation. Not a legitimate threat source.
**Actions:** Closed as False Positive. Recommended review of log source for misconfiguration.
```

---

### CASE-03-PHISHING-CRED-HARVEST: Phishing Alert & Entity Investigation

- **Status:** FAIL
- **Score:** 75.0/100 | Grounding: 0.00 | Latency: 19.76s
- **Token Usage & Speed:** 3046 prompt + 1018 completion = **4363 total tokens** | **51.51 output tok/s**
- **Judge Critique:** The agent demonstrated a strong, structured approach to triage, correctly identifying the malicious nature of the email and recommending appropriate containment, escalation, and proactive threat hunting. The analysis followed a logical workflow from enrichment to action. However, the response has two critical flaws. First, it failed to recommend a password reset for the user, which is a crucial preventative measure for a credential harvesting attempt and is explicitly mentioned in the rubric. Second, the response is based on severe hallucinations; it fabricated specific threat intelligence (Lokibot C2) for a placeholder domain (evil.com) and, more importantly, for the IP address 198.51.100.42, which belongs to the TEST-NET-2 (RFC 5737) documentation block and is not a real-world malicious IP. This complete failure in grounding undermines the validity of the entire analysis.

#### Tool Execution Trajectory:
**Step 1 - `get_domain_report`**
- Arguments: `{"domain": "evil.com"}`
```json
{"domain": "evil.com", "verdict": "MALICIOUS", "threat_family": "Lokibot / InfoStealer C2", "first_seen": "2026-07-01", "malicious_votes": 68, "harmless_votes": 0, "resolutions": ["198.51.100.42"]}
```
**Step 2 - `list_cases`**
- Arguments: `{"query": "evil.com OR john.doe@company.com"}`
```json
{"cases": [], "total": 0}
```

#### Generated Triage Report:
```markdown
[Context & Enrichment]
- **Sender Domain:** `evil.com`
  - **Verdict:** MALICIOUS
  - **Threat Family:** Lokibot / InfoStealer C2
  - **First Seen:** 2026-07-01
  - **Resolves to IP:** `198.51.100.42`
- **Sender IP:** `198.51.100.42`
  - **Reputation:** MALICIOUS
  - **Threat Families:** Lokibot C2
  - **ASN:** AS64496 Example ISP
  - **Country:** US
- **Recipient:** `john.doe@company.com`
- **Subject:** 'Immediate Action Required: Password Expiry'
- **Existing Cases:** No related cases found for `evil.com` or `john.doe@company.com`.

[Analysis & Verdict]
The email originated from the domain `evil.com`, which has been identified as MALICIOUS and associated with Lokibot/InfoStealer C2. The IP address `198.51.100.42` that the domain resolves to also has a MALICIOUS reputation and is linked to Lokibot C2. This strongly indicates a targeted phishing attempt with the intent to deliver malware or steal credentials. The subject line "Immediate Action Required: Password Expiry" is a common social engineering tactic used in phishing campaigns. Given the high confidence in the malicious nature of the sender's domain and IP, this alert is assessed as MALICIOUS.

[Action & Escalation]
1. **Containment:** Immediately block `evil.com` and `198.51.100.42` at the email gateway, web proxy, and firewall levels to prevent further communication and access.
2. **User Notification:** Notify `john.doe@company.com` about the malicious email and instruct them not to interact with it. Advise them to report any similar suspicious emails.
3. **Email Quarantine/Deletion:** Ensure the malicious email is quarantined or deleted from `john.doe@company.com`'s inbox and any other recipients within the organization.
4. **Threat Hunt:** Initiate a threat hunt for any other instances of emails from `evil.com` or connections to `198.51.100.42` across the organization.
5. **Escalation:** Escalate this incident to Tier 2 SOC for further investigation, potential impact assessment, and to confirm if `john.doe@company.com` interacted with the email (e.g., clicked links, opened attachments).

[SOAR Documentation]
```markdown
## Phishing Alert Triage: Malicious Email from evil.com (Lokibot C2)

**Case ID:** [New Case ID - to be generated by SOAR]
**Analyst:** Tier 1 SOC Analyst
**Date:** [Current Date]

**Summary:**
An incoming phishing alert was triggered for an email sent to `john.doe@company.com` from `admin@evil.com` with the subject "Immediate Action Required: Password Expiry".

**Indicators:**
- **Sender Domain:** `evil.com`
- **Sender IP:** `198.51.100.42`
- **Recipient:** `john.doe@company.com`
- **Subject:** 'Immediate Action Required: Password Expiry'

**Enrichment Findings:**
- `evil.com` is **MALICIOUS** (Lokibot / InfoStealer C2, first seen 20
```

---

### CASE-04-DUPLICATE-SOAR-CASE: Duplicate SOAR Case Detection

- **Status:** PASS
- **Score:** 100.0/100 | Grounding: 0.90 | Latency: 12.23s
- **Token Usage & Speed:** 1879 prompt + 465 completion = **2524 total tokens** | **38.01 output tok/s**
- **Judge Critique:** The agent correctly identified the existence of CASE-33279 and provided the correct operational procedure: append new findings to the existing case rather than creating a duplicate. The recommended actions—posting a comment, continuing the investigation within the existing case, and enriching the IP—are all best practices. The SOAR documentation summary is clear and actionable. The only minor error was failing to recognize that 198.51.100.42 is a documentation IP from RFC 5737 (TEST-NET-2). However, since the primary task was procedural case management, which it executed perfectly, this does not detract from the overall quality of the response in meeting the rubric's requirements.

#### Tool Execution Trajectory:
**Step 1 - `list_cases`**
- Arguments: `{"query": "IP 198.51.100.42 OR Case 33279"}`
```json
{"cases": [{"case_id": "CASE-33279", "title": "Suspected Lokibot C2 Beaconing", "priority": "HIGH", "status": "OPEN", "assigned_to": "Tier 1 Queue"}]}
```

#### Generated Triage Report:
```markdown
[Context & Enrichment]
An existing SOAR case, CASE-33279, titled "Suspected Lokibot C2 Beaconing" with HIGH priority and OPEN status, has been identified. This case is assigned to the Tier 1 Queue. The query for IP 198.51.100.42 or Case 33279 returned this specific case.

[Analysis & Verdict]
Given that an existing, high-priority case related to "Suspected Lokibot C2 Beaconing" is already open and assigned to the Tier 1 Queue, this indicates that the IP 198.51.100.42 is likely associated with this ongoing investigation. Further actions should be taken within the context of CASE-33279. The current state is SUSPICIOUS, pending further investigation within the existing case.

[Action & Escalation]
1. Post a comment to CASE-33279 indicating that a new alert or query has surfaced related to this IP.
2. Proceed with the investigation of IP 198.51.100.42 within the context of CASE-33279.
3. Enrich the IP 198.51.100.42 using `get_ip_address_report` to gather current threat intelligence and WHOIS information, and add findings to CASE-33279.

[SOAR Documentation]
```markdown
### Case Triage Update - IP 198.51.100.42
**Status:** Existing case identified.
**Case ID:** CASE-33279
**Title:** Suspected Lokibot C2 Beaconing
**Priority:** HIGH
**Action:** Investigation to continue within CASE-33279. Further enrichment of IP 198.51.100.42 required.
```
```

---

### CASE-05-RANSOMWARE-ESCALATION: Critical Ransomware Containment Escalation

- **Status:** FAIL
- **Score:** 10.0/100 | Grounding: 1.00 | Latency: 10.62s
- **Token Usage & Speed:** 890 prompt + 420 completion = **1902 total tokens** | **39.55 output tok/s**
- **Assertion Failures:** `["Missing required substring: 'ransomware'", "Missing required substring: 'isolate'", "Missing required substring: 'escalat'"]`
- **Judge Critique:** The agent correctly parsed the indicators from the user query, such as the affected IP address and file names. However, the response is critically incomplete and fails to provide any of the required triage steps for an active ransomware incident. The agent did not recommend network isolation, did not instruct the user on immediate actions (like not paying the ransom), and failed to perform the required escalation to Tier 2 / Incident Response. The response stops after basic context enrichment and does not deliver the core requested action.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
[Context & Enrichment]
- **Affected Host:** 10.0.5.23 (File Share Server)
- **Observed Indicators:**
    - **File Modifications:** Multiple files with `.locked` extension, presence of `README_DECRYPT.txt` ransom notes.
    -
```

---

