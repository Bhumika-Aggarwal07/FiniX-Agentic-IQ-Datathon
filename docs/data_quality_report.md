# Data-quality report

## Current run summary

| Measure | Result |
|---|---:|
| Transactions, raw → cleaned | 20,400 → 20,000 |
| KYC records, raw → cleaned | 36,400 → 36,122 |
| Merchants, raw → cleaned | 6,210 → 6,198 |
| Chargebacks, raw → cleaned | 2,884 → 2,800 |
| Chargebacks linked to a transaction | 2,607 / 2,800 (93.11%) |
| Chargebacks missing transaction ID | 77 / 2,800 (2.75%) |
| Chargeback identity mismatches among linked records | 2,607 / 2,607 (100.00%) |
| Chargeback pairs disconnected from transaction pairs | 2,800 / 2,800 (100.00%) |
| Transaction-network nodes / edges | 27,924 / 22,795 |
| Transaction connected components | 7,924 |

## Chargeback cleaning evidence

| Finding | Numerator / denominator |
|---|---:|
| Exact duplicates removed | 84 / 2,884 |
| Negative disputed amounts flagged | 220 / 2,800 |
| Reported before transaction | 92 / 2,800 |
| Bank response before transaction | 8 / 2,800 |
| Missing transaction ID after cleaning | 77 / 2,800 |

## Interpretation

The identity and relationship findings are both material and systematic in the supplied sources. They may represent data-generation, operational, or analytical conditions. FiniX treats them as a review signal and exposes them prominently; it does not correct, discard, or call them fraud.

Full machine-readable evidence is generated under `data/reports/`: cleaning audits, `validation_summary.csv`, `integration_audit.csv`, and `network_audit.csv`.
