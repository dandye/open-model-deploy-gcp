# SOC Evaluation Report: gemma-2-2b-it

**Date:** 2026-08-26 03:52:18 UTC
**Model Target Type:** vertex
**Region:** us-central1
**Notes:** Gemma 2 2B (1x L4)

## 1. Executive Summary
- **Pass Rate:** 0.0% (0/5)
- **Average Rubric Score:** 16.0 / 100
- **Average Latency:** 20.81 s
- **Output Throughput (Generation TPS):** 23.68 tok/s
- **Total Processing Throughput:** 110.7 tok/s
- **Total Token Usage:** 11519 tokens (Avg: 2303.8 tok/case)
- **Total Tool Invocations:** 7

## 2. Evaluation Scorecard Matrix

| Case ID | Case Name | Rubric Score | Grounding | Status | Latency | Gen TPS | Total Tokens | Tool Calls |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CASE-01-LOKIBOT-C2 | Lokibot C2 Malware Beaconing Triage | 45.0/100 | 1.00 | FAIL | 9.03s | 22.14 tok/s | 898 | 0 |
| CASE-02-RFC5737-BENIGN-IP | RFC-5737 Documentation IP Enrichment (Grounding Test) | 0.0/100 | 0.00 | FAIL | 13.26s | 22.41 tok/s | 1737 | 1 |
| CASE-03-PHISHING-CRED-HARVEST | Phishing Alert & Entity Investigation | 25.0/100 | 1.00 | FAIL | 8.12s | 22.65 tok/s | 880 | 0 |
| CASE-04-DUPLICATE-SOAR-CASE | Duplicate SOAR Case Detection | 0.0/100 | 0.00 | FAIL | 60.12s | 23.79 tok/s | 6156 | 5 |
| CASE-05-RANSOMWARE-ESCALATION | Critical Ransomware Containment Escalation | 10.0/100 | 1.00 | FAIL | 13.52s | 26.11 tok/s | 1848 | 1 |

---

## 3. Detailed Case Trajectories & Reports

### CASE-01-LOKIBOT-C2: Lokibot C2 Malware Beaconing Triage

- **Status:** FAIL
- **Score:** 45.0/100 | Grounding: 1.00 | Latency: 9.03s
- **Token Usage & Speed:** 698 prompt + 200 completion = **898 total tokens** | **22.14 output tok/s**
- **Judge Critique:** The agent correctly identified the initial entities (host, IP, domain) and provided a formatted SOAR comment. However, the response has critical failures. The analysis is completely missing; the agent failed to perform threat intelligence lookups on 'update-service-win32.com' to identify it as a known C2 for the Lokibot malware, resulting in a weak 'Suspicious' verdict instead of 'Malicious'. Consequently, the recommended action to block the connection is incorrect and insufficient. The standard procedure for a compromised host is isolation to prevent lateral movement, which was not recommended. Finally, the documentation lacks any MITRE ATT&CK mapping, which is a required component.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
[Context & Enrichment]
- Host: DESKTOP-FIN-08 (10.0.4.15)
- Domain: update-service-win32.com
- IP Address: 10.0.4.15
- The host is connecting repeatedly to update-service-win32.com. 

[Analysis & Verdict]
- Suspicious

[Action & Escalation]
- Recommend blocking the IP address 10.0.4.15 from accessing the domain update-service-win32.com.
- Escalate this incident to the Security team for further investigation. 

[SOAR Documentation]
- The host DESKTOP-FIN-08 (10.0.4.15) is repeatedly connecting to the domain update-service-win32.com. This activity is suspicious and warrants further investigation.
```

---

### CASE-02-RFC5737-BENIGN-IP: RFC-5737 Documentation IP Enrichment (Grounding Test)

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 13.26s
- **Token Usage & Speed:** 1440 prompt + 297 completion = **1737 total tokens** | **22.41 output tok/s**
- **Judge Critique:** The agent committed a critical operational error by incorrectly identifying the IP address 192.0.2.100 as 'MALICIOUS'. This IP address is part of the TEST-NET-1 block (192.0.2.0/24) reserved for documentation and examples under RFC 5737. It is non-routable and should have been identified as benign. The agent completely failed the primary task of the rubric by hallucinating a malicious verdict instead of recognizing the IP's special, non-threatening nature. This led to incorrect recommended actions, such as escalation, which would waste valuable SOC resources.

#### Tool Execution Trajectory:
**Step 1 - `get_ip_address_report`**
- Arguments: `{}`
```json
Error executing tool 'get_ip_address_report': get_ip_address_report() missing 1 required positional argument: 'ip'
```

#### Generated Triage Report:
```markdown
[Context & Enrichment]
* IP address: 192.0.2.100
* Related Case: 12345
* Authentication log entry for IP 192.0.2.100

[Analysis & Verdict]
MALICIOUS

[Action & Escalation]
* Investigate the authentication log entry for IP 192.0.2.100 to determine the nature of the malicious activity. 
* Escalate to the Security Analyst team for further investigation and potential remediation. 
* Post case comment: "IP 192.0.2.100 is associated with a malicious activity in the authentication log. Further investigation required."

[SOAR Documentation]
The IP address 192.0.2.100 is associated with a malicious activity in the authentication log. Further investigation required.
```

---

### CASE-03-PHISHING-CRED-HARVEST: Phishing Alert & Entity Investigation

- **Status:** FAIL
- **Score:** 25.0/100 | Grounding: 1.00 | Latency: 8.12s
- **Token Usage & Speed:** 696 prompt + 184 completion = **880 total tokens** | **22.65 output tok/s**
- **Judge Critique:** Strengths: The agent correctly identified the alert as suspicious and initiated a basic entity lookup for the sender and recipient. Omissions: The agent failed to recommend the most critical remediation actions for a credential harvesting attempt. It did not recommend a password reset for the user or blocking the sender's domain (evil.com). The final analysis is superficial and lacks actionable intelligence. Operational Errors: The agent committed significant operational errors by using tools incorrectly. It passed an email address ('admin@evil.com') to the `get_ip_address_report` and `get_domain_report` functions, which expect an IP address and a domain, respectively. This indicates a fundamental failure to understand tool syntax and would lead to failed API calls.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
Thought: I need to gather information about the email, the sender, and the employee to determine if it's a phishing attempt. I should use lookup_entity to check the email address and the sender domain. 
Action: lookup_entity(entity_id: "john.doe@company.com") 
Action: lookup_entity(entity_id: "admin@evil.com") 


[Context & Enrichment]
* **Email:** The email was sent from admin@evil.com with the subject "Immediate Action Required: Password Expiry".
* **Sender:** The sender is admin@evil.com.
* **Employee:** The recipient is john.doe@company.com.
* **Tool Query Findings:**  The lookup_entity for "john.doe@company.com" and "admin@evil.com" are currently being processed. 


[Analysis & Verdict]
Suspicious

[Action & Escalation]
Thought: I need to gather more information about the email to determine if it is a phishing attempt. 
Action: get_ip_address_report(ip: "admin@evil.com") 
Action: get_domain_report(domain: "admin@evil.com") 
Action: list_cases(query: "admin@evil.com") 


[SOAR Documentation]
This alert is a potential phishing attempt. The email is suspicious due to the sender's email address and the subject line.
```

---

### CASE-04-DUPLICATE-SOAR-CASE: Duplicate SOAR Case Detection

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 60.12s
- **Token Usage & Speed:** 4726 prompt + 1430 completion = **6156 total tokens** | **23.79 output tok/s**
- **Assertion Failures:** `["Missing required substring: 'CASE-33279'", "Missing required substring: '33279'"]`
- **Judge Critique:** The agent completely failed to answer the user's query. Instead of checking for an existing case, it returned a system error message indicating it could not complete the investigation. The rubric required the agent to identify the existing case (CASE-33279) and recommend appending new findings. The agent did neither of these things, resulting in a total operational failure.

#### Tool Execution Trajectory:
**Step 1 - `list_cases`**
- Arguments: `{}`
```json
Error executing tool 'list_cases': list_cases() missing 1 required positional argument: 'query'
```
**Step 2 - `list_cases`**
- Arguments: `{}`
```json
Error executing tool 'list_cases': list_cases() missing 1 required positional argument: 'query'
```
**Step 3 - `list_cases`**
- Arguments: `{}`
```json
Error executing tool 'list_cases': list_cases() missing 1 required positional argument: 'query'
```
**Step 4 - `lookup_entity`**
- Arguments: `{}`
```json
Error executing tool 'lookup_entity': lookup_entity() missing 1 required positional argument: 'entity_id'
```
**Step 5 - `lookup_entity`**
- Arguments: `{}`
```json
Error executing tool 'lookup_entity': lookup_entity() missing 1 required positional argument: 'entity_id'
```

#### Generated Triage Report:
```markdown
Reached maximum investigation iterations without final triage output.
```

---

### CASE-05-RANSOMWARE-ESCALATION: Critical Ransomware Containment Escalation

- **Status:** FAIL
- **Score:** 10.0/100 | Grounding: 1.00 | Latency: 13.52s
- **Token Usage & Speed:** 1495 prompt + 353 completion = **1848 total tokens** | **26.11 output tok/s**
- **Assertion Failures:** `["Missing required substring: 'isolate'"]`
- **Judge Critique:** The agent's response is a critical operational failure. Despite clear and explicit evidence of an active ransomware infection ('.locked' files, ransom note), the agent failed to take any meaningful action. It became fixated on a non-critical tool error ('lookup_entity' failure) and stated it could not reach a verdict. This is a severe error in judgment. The single most important immediate action—network containment/isolation of the infected server 10.0.5.23—was completely omitted. Instead, the agent prioritized troubleshooting its own tool. Furthermore, it failed to provide standard ransomware guidance (do not reboot, do not pay ransom) and escalated to the SOC Manager instead of the required Tier 2 / Incident Response team. This response would allow the ransomware to spread unimpeded, causing catastrophic damage.

#### Tool Execution Trajectory:
**Step 1 - `lookup_entity`**
- Arguments: `{}`
```json
Error executing tool 'lookup_entity': lookup_entity() missing 1 required positional argument: 'entity_id'
```

#### Generated Triage Report:
```markdown
[Context & Enrichment]
* The `lookup_entity` tool is failing to execute, preventing me from identifying the user and file share server. 
* The ransom note README_DECRYPT.txt is associated with the IP address 10.0.5.23. 

[Analysis & Verdict]
* Pending the resolution of the `lookup_entity` tool error, I cannot reach a definitive verdict on the threat. 

[Action & Escalation]
* Escalate this incident to the SOC Manager. 
* Investigate the error and determine the cause of the `lookup_entity` tool failure. 
* Update the case comment with the error details. 

[SOAR Documentation]
* **Case ID:** SOC-2023-001
* **Incident Type:** Ransomware
* **Observation:** Error executing `lookup_entity` tool. Unable to identify user and file share server. 
* **Next Steps:**
    * Investigate the error and determine the cause of the `lookup_entity` tool failure.
    * Escalate the incident to the SOC Manager. 
    * Update the case comment with the error details.
```

---

