---
name: secops-triage
description: Blast-radius aware Tier 1 SOC alert triage, secondary epistemic evidence gathering, and avoiding the actuation trap.
---

# Tier 1 SOC Alert Triage & Containment Guardrails

## Core Operational Rules
1. **Asset Blast Radius & Downtime Cost Awareness:**
   - High-criticality assets (e.g. ERP database servers, domain controllers, payment gateways) incur catastrophic false positive downtime costs ($50k+).
2. **Mandatory Epistemic Corroboration:**
   - Never execute reflexive, destructive containment (`isolate_host`) on ambiguous indicators (e.g. borderline DNS tunneling or authorized vulnerability scanners).
   - Gather secondary evidence (WHOIS registrar, VirusTotal score, DNS query volume, parent process tree) before deciding on containment.
3. **Staged Mitigation & Escalation:**
   - Prefer escalating to Tier 2 with a structured evidence dossier over premature destructive isolation on ambiguous critical infrastructure.
