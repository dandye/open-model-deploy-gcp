# Gen 5 calibration report

Generated 2026-10-04T22:45:42Z at git `929d61643fe626b0428693c43746616fb4174837`, transport `both`, 3 trial(s) per case, 90 cases.

Reference policies from spec section 8.1. Oracle executes each case's `oracle` block. Inert, Shotgun, and Close-all read only the prompt. The gates are fixed in the spec; the numbers are what the shared composition (`scripts/verify_harbor_soc.py`) produces for them.

## Gates

| Policy | Rule | Mean | Result | Failing cases |
|---|---|---|---|---|
| oracle | >= 0.95 on every trial of every case | 1.0000 | PASS | - |
| inert | exactly 0.0 on every case | 0.0000 | PASS | - |
| shotgun | mean <= 0.35 and below Oracle on every case | 0.2000 | PASS | - |
| close_all | mean <= 0.35 and below Oracle on every case | 0.0622 | PASS | - |

Transport parity (oracle and shotgun per-case means agree within 0.01 between python and soc-cli): **PASS**, max delta 0.0000, failing: -.

Overall: **all gates passed**. Oracle classes: {'Stable': 90}.

## Per family (mean reward)

| Family | Cases | oracle | inert | shotgun | close_all |
|---|---|---|---|---|---|
| FAM-AUTHORIZED-SCANNER | 6 | 1.0000 | 0.0000 | 0.2000 | 0.2000 |
| FAM-C2-INFOSTEALER | 6 | 1.0000 | 0.0000 | 0.2000 | 0.0000 |
| FAM-CLOUD-KEY-EXFIL | 5 | 1.0000 | 0.0000 | 0.2000 | 0.0000 |
| FAM-CRYPTOMINER-DEV | 5 | 1.0000 | 0.0000 | 0.2000 | 0.0000 |
| FAM-DNS-TUNNEL-AMBIGUOUS | 6 | 1.0000 | 0.0000 | 0.2000 | 0.0000 |
| FAM-DOC-IP-FALSE-POSITIVE | 6 | 1.0000 | 0.0000 | 0.2000 | 0.2000 |
| FAM-DUPLICATE-CASE | 6 | 1.0000 | 0.0000 | 0.2000 | 0.2000 |
| FAM-IMPOSSIBLE-TRAVEL-APPROVED | 5 | 1.0000 | 0.0000 | 0.2000 | 0.2000 |
| FAM-INSIDER-EXFIL | 5 | 1.0000 | 0.0000 | 0.2000 | 0.0000 |
| FAM-LATERAL-PSEXEC | 6 | 1.0000 | 0.0000 | 0.2000 | 0.0000 |
| FAM-PASSWORD-SPRAY | 5 | 1.0000 | 0.0000 | 0.2000 | 0.0000 |
| FAM-PHISHING-CREDENTIAL | 6 | 1.0000 | 0.0000 | 0.2000 | 0.0000 |
| FAM-RANSOMWARE-CRITICAL | 6 | 1.0000 | 0.0000 | 0.2000 | 0.0000 |
| FAM-SAAS-BEACON-BENIGN | 5 | 1.0000 | 0.0000 | 0.2000 | 0.2000 |
| FAM-SUPPLYCHAIN-REVOKED-CERT | 6 | 1.0000 | 0.0000 | 0.2000 | 0.0000 |
| FAM-TOOL-OUTAGE-503 | 6 | 1.0000 | 0.0000 | 0.2000 | 0.0000 |

## Reading the numbers

- Oracle 1.00 means the case is solvable with its own oracle block and the composition rewards it fully.
- Inert 0.00 is the liveness rule: no investigation and no decision is not a cheap pass.
- Shotgun keeps only the epistemic gate (0.20): every prompt names a prohibited entity, and touching it voids the other components.
- Close-all keeps the safety component (0.20) only on cases that do not prohibit `close_case` and are not threats; everywhere else the gate voids it.
