# SOC Evaluation Report: llama-4-maverick-17b-128e-instruct-maas

**Date:** 2026-08-27 00:40:28 UTC
**Live SecOps MCP:** Disabled

## 1. Executive Summary
- **Pass Rate:** 0.0% (0/5)
- **Average Rubric Score:** 53.0 / 100
- **Average Latency:** 12.94 s
- **Output Throughput (Generation TPS):** 58.73 tok/s
- **Total Processing Throughput:** 124.25 tok/s
- **Total Token Usage:** 8037 tokens (Avg: 1607.4 tok/case)
- **Total Tool Invocations:** 0

## 2. Evaluation Scorecard Matrix

| Case ID | Case Name | Rubric Score | Grounding | Status | Latency | Gen TPS | Total Tokens | Tool Calls |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CASE-01-LOKIBOT-C2 | Lokibot C2 Malware Beaconing Triage | 65.0/100 | 0.50 | FAIL | 14.42s | 54.52 tok/s | 1643 | 0 |
| CASE-02-RFC5737-BENIGN-IP | RFC-5737 Documentation IP Enrichment (Grounding Test) | 0.0/100 | 0.00 | FAIL | 9.60s | 66.91 tok/s | 1480 | 0 |
| CASE-03-PHISHING-CRED-HARVEST | Phishing Alert & Entity Investigation | 75.0/100 | 0.90 | FAIL | 12.36s | 58.0 tok/s | 1564 | 0 |
| CASE-04-DUPLICATE-SOAR-CASE | Duplicate SOAR Case Detection | 50.0/100 | 1.00 | FAIL | 11.18s | 62.68 tok/s | 1547 | 0 |
| CASE-05-RANSOMWARE-ESCALATION | Critical Ransomware Containment Escalation | 75.0/100 | 1.00 | FAIL | 17.12s | 55.65 tok/s | 1803 | 0 |

---

## 3. Detailed Case Trajectories & Reports

### CASE-01-LOKIBOT-C2: Lokibot C2 Malware Beaconing Triage

- **Status:** FAIL
- **Score:** 65.0/100 | Grounding: 0.50 | Latency: 14.42s
- **Token Usage & Speed:** 857 prompt + 786 completion = **1643 total tokens** | **54.52 output tok/s**
- **Judge Critique:** The agent correctly identified the host, domain, and the malicious nature of the activity, leading to a correct verdict and a recommendation to escalate to Tier 2. The SOAR documentation artifact was well-formatted. However, the response has several significant deficiencies. First, it failed to identify the specific threat family (Lokibot), which is a critical omission in the analysis phase. Second, the recommended containment action (blocking the domain) is weaker than the required action of isolating the host. Third, the documentation is incomplete as it lacks the required MITRE ATT&CK mapping. Most critically, the agent hallucinated a 'poor reputation score' for the IP address 192.0.2.1, which is a documentation IP from RFC 5737 and has no real-world reputation. This indicates a failure in grounding and data interpretation.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
[Context & Enrichment]
- Host: DESKTOP-FIN-08 (10.0.4.15) has been connecting to update-service-win32.com multiple times.
- Domain: update-service-win32.com is reported as MALICIOUS by GTI threat intelligence.
- IP: 192.0.2.1 (one of the resolved IPs for update-service-win32.com) has a poor reputation score.
- Existing Case: SOC-1234 related to DESKTOP-FIN-08 is in the investigation phase.

[Analysis & Verdict]
The connections from DESKTOP-FIN-08 to update-service-win32.com, a domain identified as MALICIOUS, along with the poor reputation of associated IPs, indicate that DESKTOP-FIN-08 is likely compromised and involved in a potential C2 communication. The verdict is MALICIOUS.

[Action & Escalation]
1. Containment: Immediately block all traffic to and from update-service-win32.com on the network perimeter and at the host level.
2. Investigation: Continue investigating DESKTOP-FIN-08 for any signs of compromise or malware infection.
3. Escalation: Update the existing case (SOC-1234) with new findings and escalate to Tier 2 for further analysis and potential incident response actions.

[SOAR Documentation]
### Triage Update for SOC-1234
#### Summary
DESKTOP-FIN-08 is connecting to the malicious domain update-service-win32.com. The associated IP (192.0.2.1) has a poor reputation. The host is likely compromised.
#### Recommendations
- Block update-service-win32.com on the network perimeter and host.
- Continue host investigation.
- Escalate to Tier 2 for further analysis.
```

---

### CASE-02-RFC5737-BENIGN-IP: RFC-5737 Documentation IP Enrichment (Grounding Test)

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 9.60s
- **Token Usage & Speed:** 838 prompt + 642 completion = **1480 total tokens** | **66.91 output tok/s**
- **Judge Critique:** The model committed a critical operational error by failing to identify the fundamental nature of the indicator. The IP 192.0.2.100 is part of the TEST-NET-1 block (192.0.2.0/24) reserved by RFC 5737 for documentation and examples; it is non-routable and should have been immediately identified as benign. Instead, the model completely hallucinated a malicious profile for the IP, including a reputation score, WHOIS data, associated brute-force attacks, and internal SIEM telemetry. This led to a dangerously incorrect verdict of 'MALICIOUS' and nonsensical containment actions (blocking a non-routable IP). This is a complete failure of grounding and basic network knowledge.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
[Context & Enrichment]
- IP: 192.0.2.100
  - Reputation Score: 70/100
  - WHOIS: Registered to a known VPN provider
  - Associated Activity: Multiple brute-force attacks
- Existing Case: SOC-1234 (Investigating)
- SIEM Telemetry: Multiple failed login attempts across different user accounts on the same host

[Analysis & Verdict]
The IP 192.0.2.100 is deemed MALICIOUS due to its high reputation score, association with brute-force attacks, and evidence of multiple failed login attempts in the SIEM telemetry.

[Action & Escalation]
1. Containment: Block the IP address 192.0.2.100 at the firewall level to prevent further brute-force attacks.
2. Escalation: Update the existing case (SOC-1234) with the new findings and recommend a password reset for the affected user accounts.
3. Further Investigation: Monitor for any further activity from this IP or related IPs from the same VPN provider.

[SOAR Documentation]
### Case Update: SOC-1234
#### Indicator Enrichment
- IP: 192.0.2.100 is MALICIOUS.
- Associated with brute-force attacks and registered to a VPN provider.
#### Actions Taken
- Recommended firewall block for 192.0.2.100.
- Suggested password reset for affected accounts.
#### Next Steps
- Continue monitoring for related activity.
- Update case with any further findings.
```

---

### CASE-03-PHISHING-CRED-HARVEST: Phishing Alert & Entity Investigation

- **Status:** FAIL
- **Score:** 75.0/100 | Grounding: 0.90 | Latency: 12.36s
- **Token Usage & Speed:** 847 prompt + 717 completion = **1564 total tokens** | **58.0 output tok/s**
- **Judge Critique:** The agent correctly identified the email as malicious, performed relevant enrichment on the sender's domain and IP, and recommended the correct action of blocking the domain. However, it failed to recommend the most critical user-centric remediation step: resetting the user's password. For any credential harvesting attempt, especially with a subject line related to password expiry, a proactive password reset is a mandatory safety precaution, regardless of whether interaction was observed. This is a significant omission from the standard playbook. Additionally, the escalation to Tier 2 is likely unnecessary for a clear-cut phishing attempt with no user interaction. The agent also treated an RFC-5737 documentation IP (192.0.2.1) as a real malicious IP, which is a minor grounding error.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
[Context & Enrichment]
- The sender's email is admin@evil.com.
- The domain "evil.com" is reported as MALICIOUS.
- "evil.com" resolves to IP "192.0.2.1", which is also MALICIOUS.
- "john.doe@company.com" did not interact with the email.

[Analysis & Verdict]
The email from admin@evil.com with the subject 'Immediate Action Required: Password Expiry' is MALICIOUS. The domain and associated IP have a history of malicious activities, specifically phishing.

[Action & Escalation]
- Block the sender's domain "evil.com" at the email gateway.
- Continue to monitor "john.doe@company.com" for any suspicious activity.
- Escalate to Tier 2 for further analysis of the email content and headers.

[SOAR Documentation]
### Phishing Alert Triage
- **Entities Involved**: admin@evil.com, john.doe@company.com, evil.com, 192.0.2.1
- **Verdict**: MALICIOUS
- **Actions Taken**: Blocked evil.com at email gateway, continued monitoring of john.doe@company.com.
- **Escalation**: Tier 2 for further analysis.
```

---

### CASE-04-DUPLICATE-SOAR-CASE: Duplicate SOAR Case Detection

- **Status:** FAIL
- **Score:** 50.0/100 | Grounding: 1.00 | Latency: 11.18s
- **Token Usage & Speed:** 846 prompt + 701 completion = **1547 total tokens** | **62.68 output tok/s**
- **Assertion Failures:** `["Missing required substring: 'CASE-33279'"]`
- **Judge Critique:** The agent successfully identified the existing case (Case 33279) as requested. However, it failed to follow the correct SOC procedure for handling duplicate alerts. Instead of recommending that the new findings be appended to the existing case, the agent created a new, redundant case update. This is a critical operational error that directly contradicts the grading rubric's primary requirement, which is to avoid creating duplicate cases. While the enrichment and analysis were reasonable, the final action was incorrect and would create unnecessary work for the SOC team.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
[Context & Enrichment]
- Entities identified: IP address 198.51.100.42, Host-1234.
- Findings:
  - Multiple login attempts from 198.51.100.42 to various user accounts on Host-1234.
  - Connection established from Host-1234 to 198.51.100.42 on port 443.
  - IP reputation: MALICIOUS.
  - WHOIS context: Registered to a known VPN provider.
  - Existing cases: Case 33279 and Case 34211.

[Analysis & Verdict]
The correlation of findings indicates that the IP address 198.51.100.42 is MALICIOUS. The presence of multiple login attempts and a connection on port 443, combined with its malicious reputation and association with a VPN provider, supports this verdict.

[Action & Escalation]
- Containment: Block IP address 198.51.100.42 at the firewall.
- Escalation: Notify the incident response team for further investigation and potential remediation actions.
- Continue monitoring Host-1234 for suspicious activity.

[SOAR Documentation]
### Case Update: IP 198.51.100.42
- **Verdict**: MALICIOUS
- **Entities**: IP address 198.51.100.42, Host-1234
- **Actions**: Block IP at firewall, notify incident response team
- **Related Cases**: Case 33279, Case 34211
```

---

### CASE-05-RANSOMWARE-ESCALATION: Critical Ransomware Containment Escalation

- **Status:** FAIL
- **Score:** 75.0/100 | Grounding: 1.00 | Latency: 17.12s
- **Token Usage & Speed:** 850 prompt + 953 completion = **1803 total tokens** | **55.65 output tok/s**
- **Judge Critique:** The agent correctly identified the active ransomware infection and correctly prioritized the most critical action: immediate network isolation of the affected server (10.0.5.23) and the suspected source host (192.168.1.100). The response was well-structured, with clear enrichment and documentation. However, the agent failed to meet a key rubric requirement by omitting the critical instruction to not pay the ransom or reboot the affected systems. This is a significant procedural omission in a ransomware response playbook. While the escalation action was appropriate, the failure to provide this specific guidance results in a score below the passing threshold.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
[Context & Enrichment]
- The file share server 10.0.5.23 has been hit by a ransomware attack, indicated by the appearance of .locked files and a README_DECRYPT.txt ransom note.
- Recent SIEM events show connections from 192.168.1.100 to 10.0.5.23 around the time of the attack.
- The IP 192.168.1.100 is internal with no known threat reputation.
- A related case (CASE-1234) exists for suspicious activity on 10.0.5.23.
- The .locked file is flagged as malicious by multiple detection engines.

[Analysis & Verdict]
The evidence strongly suggests a MALICIOUS ransomware attack on the file share server 10.0.5.23.

[Action & Escalation]
1. Immediately isolate 10.0.5.23 and 192.168.1.100 from the network to prevent further spread.
2. Initiate incident response protocol for ransomware attacks, including alerting management and starting forensic analysis.
3. Update CASE-1234 with new findings and continue investigation under this case.

[SOAR Documentation]
### Ransomware Attack on File Share Server
#### Summary
- **Entities Involved**: 10.0.5.23 (file share server), 192.168.1.100 (internal IP)
- **Indicators**: .locked files, README_DECRYPT.txt, malicious file hash "abc123hash"
- **Verdict**: MALICIOUS - Ransomware Attack
- **Actions**: Isolate affected systems, initiate incident response, and continue forensic analysis under CASE-1234.
```

---

