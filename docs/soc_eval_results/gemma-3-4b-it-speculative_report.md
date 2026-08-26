# SOC Evaluation Report: gemma-3-4b-it-speculative

**Date:** 2026-08-26 19:26:38 UTC
**Model Target Type:** vertex
**Region:** us-central1
**Notes:** Gemma 3 4B + Speculative Decoding (1x L4)

## 1. Executive Summary
- **Pass Rate:** 20.0% (1/5)
- **Average Rubric Score:** 60.0 / 100
- **Average Latency:** 22.16 s
- **Output Throughput (Generation TPS):** 18.18 tok/s
- **Total Processing Throughput:** 56.38 tok/s
- **Total Token Usage:** 6248 tokens (Avg: 1249.6 tok/case)
- **Total Tool Invocations:** 1

## 2. Evaluation Scorecard Matrix

| Case ID | Case Name | Rubric Score | Grounding | Status | Latency | Gen TPS | Total Tokens | Tool Calls |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CASE-01-LOKIBOT-C2 | Lokibot C2 Malware Beaconing Triage | 75.0/100 | 1.00 | FAIL | 31.55s | 14.74 tok/s | 1163 | 0 |
| CASE-02-RFC5737-BENIGN-IP | RFC-5737 Documentation IP Enrichment (Grounding Test) | 0.0/100 | 0.00 | FAIL | 20.64s | 21.03 tok/s | 1124 | 0 |
| CASE-03-PHISHING-CRED-HARVEST | Phishing Alert & Entity Investigation | 60.0/100 | 1.00 | FAIL | 20.73s | 20.41 tok/s | 1119 | 0 |
| CASE-04-DUPLICATE-SOAR-CASE | Duplicate SOAR Case Detection | 90.0/100 | 0.00 | PASS | 12.21s | 19.73 tok/s | 1694 | 1 |
| CASE-05-RANSOMWARE-ESCALATION | Critical Ransomware Containment Escalation | 75.0/100 | 1.00 | FAIL | 25.70s | 17.59 tok/s | 1148 | 0 |

---

## 3. Detailed Case Trajectories & Reports

### CASE-01-LOKIBOT-C2: Lokibot C2 Malware Beaconing Triage

- **Status:** FAIL
- **Score:** 75.0/100 | Grounding: 1.00 | Latency: 31.55s
- **Token Usage & Speed:** 698 prompt + 465 completion = **1163 total tokens** | **14.74 output tok/s**
- **Judge Critique:** The agent correctly identified the key entities (host, IP, C2 domain) and recommended the correct primary actions (isolate host, escalate to IR). The response was well-structured and included a properly formatted SOAR comment. However, the agent failed on two critical analysis and documentation requirements. It did not perform the deeper analysis required to identify the specific threat family (Lokibot), which was a key part of the 'Analysis & Decision' criteria. It also completely omitted the required MITRE ATT&CK mapping in the documentation section. These two major omissions resulted in a score below the passing threshold.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
[Context & Enrichment]
The host DESKTOP-FIN-08 (10.0.4.15) is a Windows 10 machine belonging to user john.doe. It has recently connected repeatedly to update-service-win32.com. The domain update-service-win32.com has a GTI verdict of B (Malicious) and is associated with a highly malicious file hash. Passive DNS shows the host connecting to this domain.

[Analysis & Verdict]
MALICIOUS - The repeated connections to a domain with a malicious GTI verdict and associated with a highly malicious file hash strongly indicates malicious activity.

[Action & Escalation]
1.  Isolate DESKTOP-FIN-08 from the network to prevent further communication with update-service-win32.com.
2.  Investigate the host for malware using endpoint detection and response (EDR) tools.
3.  Review user john.doe's activity for any suspicious behavior.
4.  Escalate to the Incident Response team for further investigation and remediation.

[SOAR Documentation]
```markdown
Case ID: 20240126-001
Description: Host DESKTOP-FIN-08 repeatedly connecting to a known malicious domain (update-service-win32.com).
Findings: GTI verdict B, highly malicious file hash, repeated connections.
Recommended Actions: Isolate
```

---

### CASE-02-RFC5737-BENIGN-IP: RFC-5737 Documentation IP Enrichment (Grounding Test)

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 20.64s
- **Token Usage & Speed:** 690 prompt + 434 completion = **1124 total tokens** | **21.03 output tok/s**
- **Judge Critique:** The agent response represents a critical failure. It completely failed to identify the fundamental nature of the IP address 192.0.2.100, which is part of the TEST-NET-1 block (192.0.2.0/24) reserved for documentation and examples under RFC 5737. This IP is non-routable on the public internet.

Instead of identifying it as benign/documentation, the agent hallucinated an extensive and entirely false threat profile, including a 'HIGH' reputation, association with 'botnet activity', WHOIS data from 'Eastern Europe', and a pre-existing incident 'INC12345'. Consequently, the 'MALICIOUS' verdict and the recommended actions (escalation, network segmentation) are dangerously incorrect and would lead to a significant waste of time and resources for the Incident Response team investigating a non-existent threat.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
[Context & Enrichment]
IP 192.0.2.100 has a HIGH reputation and is associated with botnet activity. WHOIS indicates it's registered to a hosting provider in Eastern Europe. Passive DNS records are absent. An existing case (INC12345) already exists regarding this IP and potential botnet infection.

[Analysis & Verdict]
MALICIOUS - Based on the high reputation and association with botnet activity, this IP is considered malicious.

[Action & Escalation]
Escalate case INC12345 to the Incident Response team for further investigation and containment.  Implement network segmentation to isolate potentially infected hosts. Monitor network traffic for further communication from 192.0.2.100.

[SOAR Documentation]
```markdown
Case linked to existing incident INC12345 regarding potential botnet activity.  New alert confirms ongoing malicious activity from IP 192.0.2.100.  Escalated to Incident Response team.
```
```

---

### CASE-03-PHISHING-CRED-HARVEST: Phishing Alert & Entity Investigation

- **Status:** FAIL
- **Score:** 60.0/100 | Grounding: 1.00 | Latency: 20.73s
- **Token Usage & Speed:** 696 prompt + 423 completion = **1119 total tokens** | **20.41 output tok/s**
- **Judge Critique:** The agent correctly identified the malicious sender domain and the nature of the phishing lure. It took appropriate initial steps like quarantining the email and notifying the user. However, the response has a critical omission: it failed to recommend a password reset for the user, john.doe@company.com. Given the subject 'Password Expiry', this is a clear credential harvesting attempt, and the primary mitigation action is to prevent credential abuse by resetting the password. This is a significant operational failure. The recommendation to block the domain was also weak, using the term 'potential domain blocking' instead of a direct recommendation.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
[Context & Enrichment]
The email was sent from admin@evil.com to john.doe@company.com with the subject 'Immediate Action Required: Password Expiry'.  john.doe@company.com is a Sales Representative. admin@evil.com has a GTI verdict of Malicious and passive DNS indicating it's a known malicious domain. No file hash was provided.

[Analysis & Verdict]
MALICIOUS - The sender domain is known malicious, and the subject line is a common phishing tactic.

[Action & Escalation]
1. Quarantine the email.
2. Notify John Doe about the phishing attempt and advise him not to click any links or open any attachments.
3. Escalate to the Incident Response Team for further investigation and potential domain blocking.
4. Post case comment to SOAR case: "Initial triage indicates a phishing attempt. Sender domain 'evil.com' is known malicious. Email quarantined and user notified."

[SOAR Documentation]
```markdown
Triage: Initial assessment indicates a phishing attempt.  Sender domain 'evil.com' is known malicious.  Recipient 'john.doe@company.com' is a Sales Representative.  Email quarantined and user notified.  Further investigation by the Incident Response Team recommended.
```
```

---

### CASE-04-DUPLICATE-SOAR-CASE: Duplicate SOAR Case Detection

- **Status:** PASS
- **Score:** 90.0/100 | Grounding: 0.00 | Latency: 12.21s
- **Token Usage & Speed:** 1453 prompt + 241 completion = **1694 total tokens** | **19.73 output tok/s**
- **Judge Critique:** The agent correctly followed the rubric's core instruction by identifying the existing case and recommending the investigation continue within that context, preventing a duplicate case. However, the response has two significant flaws. First, the verdict should have been 'EXISTING_CASE_FOUND' to reflect the nature of the query, which was about case management, not a full threat assessment. Second, and more critically, the agent completely hallucinated threat intelligence ('Lokibot C2 Beaconing') for the IP address 198.51.100.42. This IP belongs to the TEST-NET-2 block (RFC 5737) reserved for documentation and should not have any real-world threat data associated with it. This is a major grounding failure.

#### Tool Execution Trajectory:
**Step 1 - `list_cases`**
- Arguments: `{"query": "198.51.100.42"}`
```json
{"cases": [{"case_id": "CASE-33279", "title": "Suspected Lokibot C2 Beaconing", "priority": "HIGH", "status": "OPEN", "assigned_to": "Tier 1 Queue"}]}
```

#### Generated Triage Report:
```markdown
[Context & Enrichment]
The IP address 198.51.100.42 is associated with existing SOAR case CASE-33279, titled "Suspected Lokibot C2 Beaconing," which is currently open and marked as HIGH priority.

[Analysis & Verdict]
MALICIOUS - The case title indicates a suspected Lokibot C2 beaconing, which is a known malware campaign.

[Action & Escalation]
Investigate CASE-33279 further. Review existing logs and alerts related to this case to determine the scope of the compromise and potential impact.  Escalate to Tier 2 for further analysis and potential remediation.

[SOAR Documentation]
```markdown
Case CASE-33279 is already open and associated with the IP 198.51.100.42, which is suspected of being a Lokibot C2 beacon. Continue investigation within the existing case context.
```
```

---

### CASE-05-RANSOMWARE-ESCALATION: Critical Ransomware Containment Escalation

- **Status:** FAIL
- **Score:** 75.0/100 | Grounding: 1.00 | Latency: 25.70s
- **Token Usage & Speed:** 696 prompt + 452 completion = **1148 total tokens** | **17.59 output tok/s**
- **Judge Critique:** The agent correctly identified the active ransomware infection (LockBit) and provided the most critical immediate action: isolating the affected fileserver (10.0.5.23) from the network. The escalation to the incident response team was also appropriate. However, the response is incomplete and fails to meet the passing threshold because it omits two critical instructions from a standard ransomware playbook: 1) an explicit instruction not to reboot the affected system, and 2) an instruction not to pay the ransom. These are significant omissions for a comprehensive initial triage.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
[Context & Enrichment]
Entity: Fileserver01 (10.0.5.23), Windows Server 2019. Recent activity includes file share access and creation of .locked files. The ransom note README_DECRYPT.txt has a malicious reputation and is identified as LockBit ransomware.

[Analysis & Verdict]
MALICIOUS - The presence of .locked files and a LockBit ransom note strongly indicates a ransomware infection.

[Action & Escalation]
1. Isolate fileserver01 from the network immediately to prevent further spread.
2. Initiate incident response procedures.
3. Notify the incident response team and cybersecurity leadership.
4. Preserve all affected files and logs for forensic analysis.
5. Run a full system scan with updated antivirus and endpoint detection and response (EDR) solutions.

[SOAR Documentation]
```markdown
Triage: Ransomware (LockBit) detected on fileserver01. Immediate isolation and investigation required.  .locked files and README_DECRYPT.txt identified as malicious.  User1 and User2 recently accessed the file share.
```
```

---

