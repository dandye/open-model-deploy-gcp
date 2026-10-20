# Continual Improvement Library (EXPERIENCE.md)

Contrast-verified lessons extracted from isolated runbook probes.
Confounded multi-component edits are excluded.

## 1. Runbook refinement for lateral_movement_hunt_psexec_wmi.md
- **Component**: `lateral_movement_hunt_psexec_wmi.md` (`COMPOSED`)
- **Attribution**: `helped` (mean delta `+0.2187`)
- **Lesson**: Updated lateral_movement_hunt_psexec_wmi.md (1074 -> 281 words) lifting validation fitness by +0.2187 with zero regressions: Use `secops-mcp.get_threat_intel` on T1021.002 (Remote Services: SMB/Windows Admin Shares) and T1047 (Windows Management Instrumentation) to inform query logic.; Formulate and execute UDM hunt queries using `secops-mc...
- **Evidence**: Candidate 2 (round 1, harness2) cleared tau_accept (0.0150) on 1 evaluated cases.
- **Confidence**: `high`

## 2. Runbook refinement for malware_triage.md
- **Component**: `malware_triage.md` (`COMPOSED`)
- **Attribution**: `helped` (mean delta `+0.0528`)
- **Lesson**: Updated malware_triage.md (843 -> 336 words) lifting validation fitness by +0.0528 with zero regressions: Get File Reputation:** Call `gti-mcp.get_file_report` with `hash=<file_hash>` to get the file's threat intelligence report (`<gti_report>`).; Check Host & Execution Context:** Call `secops-mcp.lookup_entity` on the al...
- **Evidence**: Candidate 2 (round 1, harness2) cleared tau_accept (0.0150) on 7 evaluated cases.
- **Confidence**: `high`
