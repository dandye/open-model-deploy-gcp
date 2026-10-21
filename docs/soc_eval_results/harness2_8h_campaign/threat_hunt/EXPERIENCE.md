# Continual Improvement Library (EXPERIENCE.md)

Contrast-verified lessons extracted from isolated runbook probes.
Confounded multi-component edits are excluded.

## 1. Track 2 Threat Hunt refinement (round 1)
- **Component**: `gti_collection_threat_hunt.md` (`DOM`)
- **Attribution**: `helped` (mean delta `+0.0782`)
- **Lesson**: Updated gti_collection_threat_hunt.md (350 -> 347 words) lifting validation fitness by +0.0782 with zero regressions: Call `get_collection_report` and `get_entities_related_to_a_collection` (or `get_domain_report` and `get_entities_related_to_a_domain`) to extract indicators.; Call `get_ioc_matches` and `search_security_events` for extracted indicators, starting with `hours_back=72`.
- **Evidence**: Round 1 (DOM) evaluated across 4 Ursnif GTI hunt scenarios.
- **Confidence**: `high`
