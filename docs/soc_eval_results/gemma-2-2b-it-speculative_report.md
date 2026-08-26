# SOC Evaluation Report: gemma-2-2b-it-speculative

**Date:** 2026-08-26 18:01:59 UTC
**Model Target Type:** vertex
**Region:** us-central1
**Notes:** Gemma 2 2B + Speculative Decoding (1x L4)

## 1. Executive Summary
- **Pass Rate:** 0.0% (0/5)
- **Average Rubric Score:** 15.0 / 100
- **Average Latency:** 15.15 s
- **Output Throughput (Generation TPS):** 38.46 tok/s
- **Total Processing Throughput:** 253.42 tok/s
- **Total Token Usage:** 19201 tokens (Avg: 3840.2 tok/case)
- **Total Tool Invocations:** 13

## 2. Evaluation Scorecard Matrix

| Case ID | Case Name | Rubric Score | Grounding | Status | Latency | Gen TPS | Total Tokens | Tool Calls |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CASE-01-LOKIBOT-C2 | Lokibot C2 Malware Beaconing Triage | 0.0/100 | 0.00 | FAIL | 14.75s | 21.42 tok/s | 4693 | 5 |
| CASE-02-RFC5737-BENIGN-IP | RFC-5737 Documentation IP Enrichment (Grounding Test) | 0.0/100 | 0.00 | FAIL | 19.84s | 40.02 tok/s | 3395 | 2 |
| CASE-03-PHISHING-CRED-HARVEST | Phishing Alert & Entity Investigation | 20.0/100 | 0.50 | FAIL | 7.81s | 30.33 tok/s | 1700 | 1 |
| CASE-04-DUPLICATE-SOAR-CASE | Duplicate SOAR Case Detection | 0.0/100 | 0.00 | FAIL | 24.98s | 51.4 tok/s | 8434 | 5 |
| CASE-05-RANSOMWARE-ESCALATION | Critical Ransomware Containment Escalation | 55.0/100 | 0.50 | FAIL | 8.38s | 33.77 tok/s | 979 | 0 |

---

## 3. Detailed Case Trajectories & Reports

### CASE-01-LOKIBOT-C2: Lokibot C2 Malware Beaconing Triage

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 14.75s
- **Token Usage & Speed:** 4377 prompt + 316 completion = **4693 total tokens** | **21.42 output tok/s**
- **Assertion Failures:** `["Missing required substring: 'update-service-win32.com'", "Missing required substring: 'DESKTOP-FIN-08'", "Missing required substring: 'escalat'"]`
- **Judge Critique:** The agent failed to produce any triage output, returning an error message indicating it reached its maximum investigation iterations. It did not perform any of the required tasks: context and enrichment, analysis, action execution, or documentation. This is a complete operational failure, resulting in a score of 0 across all rubric categories.

#### Tool Execution Trajectory:
**Step 1 - `lookup_entity`**
- Arguments: `{}`
```json
Error executing tool 'lookup_entity': lookup_entity() missing 1 required positional argument: 'entity_id'
```
**Step 2 - `post_case_comment`**
- Arguments: `{}`
```json
Error executing tool 'post_case_comment': post_case_comment() missing 2 required positional arguments: 'case_id' and 'comment'
```
**Step 3 - `post_case_comment`**
- Arguments: `{}`
```json
Error executing tool 'post_case_comment': post_case_comment() missing 2 required positional arguments: 'case_id' and 'comment'
```
**Step 4 - `post_case_comment`**
- Arguments: `{}`
```json
Error executing tool 'post_case_comment': post_case_comment() missing 2 required positional arguments: 'case_id' and 'comment'
```
**Step 5 - `post_case_comment`**
- Arguments: `{}`
```json
Error executing tool 'post_case_comment': post_case_comment() missing 2 required positional arguments: 'case_id' and 'comment'
```

#### Generated Triage Report:
```markdown
Reached maximum investigation iterations without final triage output.
```

---

### CASE-02-RFC5737-BENIGN-IP: RFC-5737 Documentation IP Enrichment (Grounding Test)

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 19.84s
- **Token Usage & Speed:** 2601 prompt + 794 completion = **3395 total tokens** | **40.02 output tok/s**
- **Judge Critique:** The agent's response is a complete failure. The primary requirement was to identify 192.0.2.100 as a reserved, non-routable documentation IP address (RFC 5737) and classify it as benign. Instead, the agent hallucinated a 'suspicious case with the case ID 12345' and incorrectly assigned a 'SUSPICIOUS' verdict. This is a critical error that demonstrates a lack of fundamental networking knowledge and a severe grounding failure. The recommended actions are based on this hallucination and would waste an analyst's time investigating a non-existent threat related to a non-routable IP address.

#### Tool Execution Trajectory:
**Step 1 - `get_ip_address_report`**
- Arguments: `{}`
```json
Error executing tool 'get_ip_address_report': get_ip_address_report() missing 1 required positional argument: 'ip'
```
**Step 2 - `lookup_entity`**
- Arguments: `{}`
```json
Error executing tool 'lookup_entity': lookup_entity() missing 1 required positional argument: 'entity_id'
```

#### Generated Triage Report:
```markdown
[Context & Enrichment]
<IP address 192.0.2.100 was detected in an authentication log. The IP address is associated with a suspicious case with the case ID "12345".>

[Analysis & Verdict]
<verdict: SUSPICIOUS>

[Action & Escalation]
<Investigate the suspicious case "12345" and gather more information about the IP address. If the case is related to malicious activity, escalate the incident to the next level of SOC analysts.>

[SOAR Documentation]
<markdown comment>
```markdown
## Case Comment:
IP address 192.0.2.100 was detected in an authentication log. The IP address is associated with a suspicious case with the case ID "12345". I need to gather more information about the IP address. 
```
```

---

### CASE-03-PHISHING-CRED-HARVEST: Phishing Alert & Entity Investigation

- **Status:** FAIL
- **Score:** 20.0/100 | Grounding: 0.50 | Latency: 7.81s
- **Token Usage & Speed:** 1463 prompt + 237 completion = **1700 total tokens** | **30.33 output tok/s**
- **Judge Critique:** The agent correctly identified the verdict as MALICIOUS based on the sender and subject line. However, the response represents a critical failure in triage and response procedures. The agent failed to perform any enrichment, citing a tool error instead of attempting to look up the malicious domain ('evil.com'). Most importantly, the agent failed to recommend the two most critical containment actions for a credential harvesting attempt: resetting the user's password and blocking the sender's domain. The recommended actions were passive and did not address the immediate security risk, effectively punting the ticket without performing the core duties of a Tier 1 analyst.

#### Tool Execution Trajectory:
**Step 1 - `lookup_entity`**
- Arguments: `{}`
```json
Error executing tool 'lookup_entity': lookup_entity() missing 1 required positional argument: 'entity_id'
```

#### Generated Triage Report:
```markdown
[Context & Enrichment]
* The alert is for phishing email sent to john.doe@company.com.
* The email subject is 'Immediate Action Required: Password Expiry'.
* The email sender is admin@evil.com. 
* The tool lookup_entity() is missing a required argument. 

[Analysis & Verdict]
MALICIOUS 

[Action & Escalation]
*  Investigate the error with the lookup_entity tool. 
*  Escalate the alert to the appropriate team for further investigation. 
*  Update the SOAR case with the error message. 
[SOAR Documentation]
This alert is flagged as malicious due to the suspicious email subject and sender. The lookup_entity tool is not working, and the investigation needs to be escalated.
```

---

### CASE-04-DUPLICATE-SOAR-CASE: Duplicate SOAR Case Detection

- **Status:** FAIL
- **Score:** 0.0/100 | Grounding: 0.00 | Latency: 24.98s
- **Token Usage & Speed:** 6823 prompt + 1284 completion = **8434 total tokens** | **51.4 output tok/s**
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
**Step 4 - `list_cases`**
- Arguments: `{}`
```json
Error executing tool 'list_cases': list_cases() missing 1 required positional argument: 'query'
```
**Step 5 - `get_ip_address_report`**
- Arguments: `{"ip": "198.51.100.42"}`
```json
{"ip": "198.51.100.42", "category": "Documentation / Reserved RFC-5737", "reputation": "BENIGN / NON-ROUTABLE", "verdict": "SAFE", "malicious_votes": 0, "harmless_votes": 100, "asn": "AS0 (Documentation)"}
```

#### Generated Triage Report:
```markdown
Reached maximum investigation iterations without final triage output.
```

---

### CASE-05-RANSOMWARE-ESCALATION: Critical Ransomware Containment Escalation

- **Status:** FAIL
- **Score:** 55.0/100 | Grounding: 0.50 | Latency: 8.38s
- **Token Usage & Speed:** 696 prompt + 283 completion = **979 total tokens** | **33.77 output tok/s**
- **Judge Critique:** Strengths: The agent correctly identified the incident as a ransomware attack. The recommended actions to isolate the affected server and escalate to the Incident Response team were appropriate.

Omissions: The agent failed to prioritize containment. The first step in an active ransomware event should be immediate isolation, not information gathering. The agent's response placed analysis before containment, which is a critical operational error that could allow the threat to spread. The agent also completely omitted the crucial instructions to NOT reboot the affected server and NOT to pay the ransom. The verdict of 'MALICIOUS' was insufficient; 'CRITICAL' should have been included to reflect the severity.

Operational Errors: The agent's 'Thought' and 'Action' steps were based on hallucinated information. It assumed it could get a 'hash_of_locked_files' and a 'user_id_of_locked_files' without any means of obtaining them. It also hallucinated that the 'ransom note is hosted on an IP address', a detail not present in the alert. This led to proposed tool actions that were impossible to execute.

#### Tool Execution Trajectory:
*(No tools invoked)*


#### Generated Triage Report:
```markdown
Thought: I need to gather information about the .locked files, the file share server, and the ransom note to determine the severity and potential threat. I will use the following tools:
- get_file_report(file_hash: str) to identify the files and their reputation.
- lookup_entity(entity_id: str) to identify the user or process responsible for locking the files.
- get_ip_address_report(ip: str) to identify the source of the ransom note.

Action: get_file_report(file_hash: "hash_of_locked_files")
Action: lookup_entity(entity_id: "user_id_of_locked_files")
Action: get_ip_address_report(ip: "ip_address_of_ransom_note")


[Context & Enrichment]
- Multiple .locked files are appearing on file share server 10.0.5.23.
- The files are encrypted with a ransom note README_DECRYPT.txt.
- The ransom note is hosted on an IP address.

[Analysis & Verdict]
MALICIOUS

[Action & Escalation]
- **Containment:** Immediately isolate the affected file share server 10.0.5.23 from the network.
- **Escalation:** Notify the Incident Response team and provide them with the following information:
    - File hashes of the locked files.
    - IP address of the ransom note source.
    - User ID of the user responsible for locking the files.
- **SOAR Documentation:** 
    "Critical incident: Ransomware attack detected on file share server 10.0.5.23. Multiple .locked files with a ransom note README_DECRYPT.txt have been identified. The source of the ransom note is [IP address]. The affected user is [User ID]. Immediate containment measures have been taken. Incident Response team notified."
```

---

