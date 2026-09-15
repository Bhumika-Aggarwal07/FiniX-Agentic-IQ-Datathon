# Cleaning rules

## Shared principles

1. Raw files are read only.
2. Only exact source-row duplicates are removed.
3. IDs are held as strings and formatting is normalized without truncating their body.
4. Missing values are retained; FiniX does not fabricate replacements.
5. Invalid negative monetary values become missing and remain flagged.
6. Unsupported timestamps are flagged and become missing in derived outputs.

## Dataset-specific rules

| Dataset | Rules |
|---|---|
| Transactions | Normalizes `TXN`, `USR`, `MCH`, and `UTR` identifiers; parses INR amounts; canonicalizes completed/failed/pending status; validates four-digit MCCs; parses documented mixed timestamps. |
| KYC | Normalizes `USR`; validates PAN/Aadhaar shapes; parses income; uppercases categorical fields; does not expose sensitive identity values to the dashboard. Ambiguous dates are not guessed. |
| Merchants | Normalizes `MCH`; validates MCC and settlement-account shape; parses ticket size and onboarding date; canonicalizes merchant status. |
| Chargebacks | Normalizes `CBK`, `TXN`, `USR`, and `MCH`; parses disputed amount and timestamps; flags impossible chronology; maps known category variants; preserves original chargeback identities. |

Every cleaner writes `data/reports/<dataset>_cleaning_audit.csv`, where each finding includes numerator, denominator, and percentage.
