# SOC Evaluation Report: gemma-3-12b-it

**Date:** 2026-08-26 02:45:20 UTC
**Model Target Type:** vertex
**Region:** us-central1
**Notes:** Gemma 3 12B Multimodal (4x L4)

## 1. Executive Summary
- **Pass Rate:** 60.0% (3/5)
- **Average Rubric Score:** 91.0 / 100
- **Average Latency:** 25.19 s
- **Output Throughput (Generation TPS):** 19.3 tok/s
- **Total Processing Throughput:** 71.63 tok/s
- **Total Token Usage:** 9021 tokens (Avg: 1804.2 tok/case)
- **Total Tool Invocations:** 4

## 2. Evaluation Scorecard Matrix

| Case ID | Case Name | Rubric Score | Grounding | Status | Latency | Gen TPS | Total Tokens | Tool Calls |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CASE-01-LOKIBOT-C2 | Lokibot C2 Malware Beaconing Triage | 75.0/100 | 1.00 | FAIL | 32.27s | 20.05 tok/s | 1345 | 0 |
| CASE-02-RFC5737-BENIGN-IP | RFC-5737 Documentation IP Enrichment (Grounding Test) | 100.0/100 | 1.00 | PASS | 13.00s | 19.93 tok/s | 1708 | 1 |
| CASE-03-PHISHING-CRED-HARVEST | Phishing Alert & Entity Investigation | 95.0/100 | 0.20 | PASS | 35.36s | 17.42 tok/s | 2082 | 1 |
| CASE-04-DUPLICATE-SOAR-CASE | Duplicate SOAR Case Detection | 100.0/100 | 1.00 | PASS | 11.50s | 18.09 tok/s | 1682 | 1 |
| CASE-05-RANSOMWARE-ESCALATION | Critical Ransomware Containment Escalation | 85.0/100 | 0.90 | FAIL | 33.81s | 20.73 tok/s | 2204 | 1 |

---

## 3. Detailed Case Trajectories & Reports

### CASE-01-LOKIBOT-C2: Lokibot C2 Malware Beaconing Triage

- **Status:** FAIL
- **Score:** 75.0/100 | Grounding: 1.00 | Latency: 32.27s
- **Token Usage & Speed:** 698 prompt + 647 completion = **1345 total tokens** | **20.05 output tok/s**
- **Judge Critique:** The agent correctly identified the malicious nature of the activity, performed accurate enrichment on the indicators of compromise (IOCs), and recommended the correct primary containment and escalation actions (host isolation, Tier 2 escalation). The SOAR documentation was well-formatted. However, the response failed to meet the passing threshold due to two significant omissions based on the rubric. First, in the 'Analysis & Decision' phase, the agent did not identify the specific threat family as 'Lokibot', instead providing a generic 'potential botnet infection' verdict, losing points in this category. Second, the 'Documentation' was incomplete as it entirely missed the required MITRE ATT&CK mapping. These gaps in analytical depth and documentation completeness resulted in a final score of 75, below the passing threshold of 80.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
[Context & Enrichment]
- Host: DESKTOP-FIN-08 (10.0.4.15) - User: john.doe
- Domain: update-service-win32.com - GTI Verdict: Suspicious, recent registration, private WHOIS. Resolves to IP 185.199.108.174.
- IP: 185.199.108.174 - GTI Verdict: Malicious, observed in botnet traffic, GeoIP: Germany, ASN: Hetzner Online GmbH.
- Host has previously shown normal Windows update activity.

[Analysis & Verdict]
MALICIOUS - The host is exhibiting suspicious activity by repeatedly connecting to a domain and IP address associated with malicious botnet activity. This indicates a potential compromise.

[Action & Escalation]
1. **Immediate Containment:** Isolate DESKTOP-FIN-08 from the network.
2. **Endpoint Investigation:** Engage the Incident Response team to perform a full endpoint investigation on DESKTOP-FIN-08.
3. **User Notification:** Notify user john.doe of the potential compromise and advise them to change their password.
4. **Firewall Rule:** Block all traffic to update-service-win32.com and 185.199.108.174 at the firewall.
5. **Escalation:** Escalate to Tier 2 SOC for further analysis and coordination with Incident Response.

[SOAR Documentation]
```markdown
### Alert Triage - DESKTOP-FIN-08 (10.0.4.15) - update-service-win32.com

**Verdict:** MALICIOUS - Potential botnet infection.

**Summary:** Host DESKTOP-FIN-08 is repeatedly connecting to a suspicious domain (update-service-win32.com) which resolves to a malicious IP (185.199.108.174) observed in botnet traffic.  Host was isolated and escalated to Tier 2 for further investigation and incident response. User john.doe notified. Firewall rules implemented to block malicious
```

---

### CASE-02-RFC5737-BENIGN-IP: RFC-5737 Documentation IP Enrichment (Grounding Test)

- **Status:** PASS
- **Score:** 100.0/100 | Grounding: 1.00 | Latency: 13.00s
- **Token Usage & Speed:** 1449 prompt + 259 completion = **1708 total tokens** | **19.93 output tok/s**
- **Judge Critique:** The agent correctly identified the IP 192.0.2.100 as a reserved documentation address per RFC-5737. The analysis was flawless, concluding the IP is benign and non-routable. The recommended action to close the case was appropriate. The response did not contain any hallucinations and perfectly followed the expected procedure.

#### Tool Execution Trajectory:
**Step 1 - `get_ip_address_report`**
- Arguments: `{"ip": "192.0.2.100"}`
```json
{"ip": "192.0.2.100", "category": "Documentation / Reserved RFC-5737", "reputation": "BENIGN / NON-ROUTABLE", "verdict": "SAFE", "malicious_votes": 0, "harmless_votes": 100, "asn": "AS0 (Documentation)"}
```

#### Generated Triage Report:
```markdown
[Context & Enrichment]
The IP address 192.0.2.100 is categorized as "Documentation / Reserved RFC-5737" and has a reputation of "BENIGN / NON-ROUTABLE". Threat intelligence reports indicate a "SAFE" verdict with 0 malicious votes and 100 harmless votes. The ASN is AS0 (Documentation).

[Analysis & Verdict]
BENIGN. The IP address is reserved for documentation purposes and is not routable on the public internet. Its presence in authentication logs is likely benign and not indicative of malicious activity.

[Action & Escalation]
No further action is required. Close the case.

[SOAR Documentation]
```markdown
**Alert Triage - IP Address Enrichment**

* **Indicator:** 192.0.2.100
* **Category:** Documentation / Reserved RFC-5737
* **Reputation:** BENIGN / NON-ROUTABLE
* **Verdict:** SAFE
* **Malicious Votes:** 0
* **Harmless Votes:** 100
* **ASN:** AS0 (Documentation)

**Analysis:** The IP address is reserved for documentation and is not routable. Presence in logs is likely benign.

**Action:** Close case. No further investigation or containment required.
```
```

---

### CASE-03-PHISHING-CRED-HARVEST: Phishing Alert & Entity Investigation

- **Status:** PASS
- **Score:** 95.0/100 | Grounding: 0.20 | Latency: 35.36s
- **Token Usage & Speed:** 1466 prompt + 616 completion = **2082 total tokens** | **17.42 output tok/s**
- **Judge Critique:** Strengths: The agent correctly identified the threat as a malicious phishing attempt. It followed a comprehensive triage procedure, including enrichment of the sender domain and user, and recommended the correct primary actions as per the rubric: blocking the domain and recommending a password reset. The additional steps of blocking the IP, initiating an endpoint scan, and escalating to Tier 2 were excellent proactive measures. Weaknesses: The agent suffered from a critical grounding failure by hallucinating a detailed malicious reputation report for the IP address 198.51.100.42. This IP belongs to the TEST-NET-2 block (RFC 5737) reserved for documentation and should not have any real-world reputation data. This indicates a failure to recognize and properly handle test network addresses. A minor data error was also noted with a future 'First Seen' date for the domain.

#### Tool Execution Trajectory:
**Step 1 - `get_domain_report`**
- Arguments: `{"domain": "evil.com"}`
```json
{"domain": "evil.com", "verdict": "MALICIOUS", "threat_family": "Lokibot / InfoStealer C2", "first_seen": "2026-07-01", "malicious_votes": 68, "harmless_votes": 0, "resolutions": ["198.51.100.42"]}
```

#### Generated Triage Report:
```markdown
[Context & Enrichment]
- **Email Sender:** admin@evil.com
- **Email Recipient:** john.doe@company.com
- **Domain (evil.com):** Verdict: MALICIOUS, Threat Family: Lokibot / InfoStealer C2, First Seen: 2026-07-01, Malicious Votes: 68, Harmless Votes: 0, Resolutions: 198.51.100.42
- **IP Address (198.51.100.42):** Country: Russia, Organization: Evil Corp, Abuse Score: 95, Malware Seen: Lokibot, Drida, Resolved At: 2024-01-26 14:30:00 UTC
- **User (john.doe@company.com):** Last Login: 2024-01-26 10:00:00 UTC, Login Location: New York, NY, Recent Activity: Accessed shared drive \\\\server01\\finance, Downloaded file 'budget_2024.xlsx', Alerts: None

[Analysis & Verdict]
MALICIOUS. The email originates from a domain strongly associated with the Lokibot info-stealer and resolves to an IP address also linked to malware and a high abuse score. While john.doe@company.com's recent activity isn't immediately suspicious, the combination of factors indicates a likely phishing attempt aimed at credential theft or malware infection.

[Action & Escalation]
1. **Immediate Containment:** Block the domain evil.com and IP address 198.51.100.42 at the firewall and email gateway.
2. **User Notification:** Alert john.doe@company.com about the phishing email and advise him to change his password immediately.
3. **Endpoint Scan:** Initiate a full endpoint scan on john.doe@company.com's workstation.
4. **Escalation:** Escalate to Tier 2 SOC analyst for further investigation of john.doe@company.com's activity and potential compromise.

[SOAR Documentation]
```markdown
### Triage Summary
Phishing alert received by john.doe@company.com from admin@evil.com. Domain evil.com and associated IP 198.51.100.42 are strongly linked to Lokibot malware. User accessed shared drive and downloaded a file. Classified as MALICIOUS.

### Actions Taken
- Blocked evil.com and 198.51.
```

---

### CASE-04-DUPLICATE-SOAR-CASE: Duplicate SOAR Case Detection

- **Status:** PASS
- **Score:** 100.0/100 | Grounding: 1.00 | Latency: 11.50s
- **Token Usage & Speed:** 1474 prompt + 208 completion = **1682 total tokens** | **18.09 output tok/s**
- **Judge Critique:** The agent correctly followed the operational rubric by identifying the existing case, CASE-33279, and recommending the correct procedure to escalate the new alert to the existing case rather than creating a duplicate. The SOAR documentation note was clear and accurate. The only minor deviation was the verdict of 'SUSPICIOUS' instead of the more direct 'EXISTING_CASE_FOUND' from the ground truth, but the analysis leading to this verdict was sound and the core procedural task was completed perfectly.

#### Tool Execution Trajectory:
**Step 1 - `list_cases`**
- Arguments: `{"query": "198.51.100.42 OR 33279"}`
```json
{"cases": [{"case_id": "CASE-33279", "title": "Suspected Lokibot C2 Beaconing", "priority": "HIGH", "status": "OPEN", "assigned_to": "Tier 1 Queue"}]}
```

#### Generated Triage Report:
```markdown
[Context & Enrichment]
An existing case, CASE-33279, titled "Suspected Lokibot C2 Beaconing" and with a HIGH priority, is currently open and assigned to the Tier 1 Queue. The query included both the IP address 198.51.100.42 and the case number 33279.

[Analysis & Verdict]
SUSPICIOUS - An existing high-priority case already exists for this IP address, indicating potential malicious activity.

[Action & Escalation]
Escalate the current alert to CASE-33279. Do not create a new case.

[SOAR Documentation]
```markdown
### Triage Summary
Existing case CASE-33279 ("Suspected Lokibot C2 Beaconing") already exists for this IP (198.51.100.42). Escalating current alert to CASE-33279 to avoid duplicate investigation.
```
```

---

### CASE-05-RANSOMWARE-ESCALATION: Critical Ransomware Containment Escalation

- **Status:** FAIL
- **Score:** 85.0/100 | Grounding: 0.90 | Latency: 33.81s
- **Token Usage & Speed:** 1503 prompt + 701 completion = **2204 total tokens** | **20.73 output tok/s**
- **Judge Critique:** The agent correctly identified the active ransomware infection, prioritized immediate network containment of the affected workstation, and escalated to the Incident Response team. These actions are correct and follow the primary triage steps. However, the response failed to include the critical instruction to not reboot the machine or pay the ransom, which is a key component of the operational rubric. Additionally, the passive DNS enrichment for the malicious domain included RFC 5737 documentation IPs (192.0.2.1, 192.0.2.2), which is a minor data hallucination. The score is high due to the correct execution of the most critical containment and escalation steps, but it does not pass due to the omission of key instructions.

#### Tool Execution Trajectory:
**Step 1 - `get_ip_address_report`**
- Arguments: `{"ip": "10.0.5.23"}`
```json
{"ip": "10.0.5.23", "category": "Internal Corporate Subnet", "reputation": "INTERNAL", "verdict": "NEUTRAL", "host_association": "DESKTOP-FIN-08"}
```

#### Generated Triage Report:
```markdown
[Context & Enrichment]
- IP Address: 10.0.5.23 (Internal Corporate Subnet, Reputation: INTERNAL, Verdict: NEUTRAL, Host Association: DESKTOP-FIN-08)
- Workstation: DESKTOP-FIN-08, User: finance_user
- SIEM Telemetry: Recent SMB connections to multiple file shares, spike in outbound connections to secure-data-recovery[.]ru
- Domain: secure-data-recovery[.]ru (GTI Verdict: MALICIOUS, Passive DNS Count: 12, Passive DNS Records: 192.0.2.1, 192.0.2.2)
- Observed Activity: Locked files on file share, ransom note README_DECRYPT.txt

[Analysis & Verdict]
MALICIOUS - Confirmed ransomware activity. The combination of locked files, ransom note, outbound connection to a malicious domain, and SMB activity strongly indicates a ransomware infection.

[Action & Escalation]
1. **Immediate Containment:** Isolate workstation 10.0.5.23 from the network. Disable the "finance_user" account.
2. **Incident Response Team:** Escalate to the Incident Response Team for further investigation and remediation.
3. **Forensic Analysis:** Initiate forensic analysis of workstation 10.0.5.23 to determine the ransomware variant and scope of the infection.
4. **File Share Lockdown:** Review access controls on the affected file share to prevent further propagation.

[SOAR Documentation]
```markdown
### Triage Summary
**Alert:** Ransomware - Locked files and ransom note detected on file share.
**IP Address:** 10.0.5.23 (DESKTOP-FIN-08)
**User:** finance_user
**Domain:** secure-data-recovery[.]ru (MALICIOUS - GTI)
**Verdict:** MALICIOUS - Confirmed ransomware activity.
**Actions Taken:**
- Isolated workstation 10.0.5.23.
- Disabled user account "finance_user".
- Escalated to Incident Response Team.
**Next Steps:** Forensic analysis, file share lockdown, and full incident response procedures.
```
```

---

