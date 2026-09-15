# FiniX data dictionary

This project uses actual source schemas. Derived tables retain source fields and add the following analytical columns.

## Source datasets

| Dataset | Key fields | Business fields | Sensitive fields excluded from dashboard |
|---|---|---|---|
| Transactions | `txn_id`, `user_id`, `merchant_id`, `utr` | `timestamp`, `amount`, `mcc`, `status` | None identified. |
| Chargebacks | `complaint_id`, `txn_id`, `user_id`, `merchant_id` | timestamps, `disputed_amount`, reason, severity, resolution, channel | Complaint text is retained in data but not shown by default. |
| KYC | `user_id` | geography, income, occupation, signup, KYC status, risk segment | `full_name`, `pan`, `aadhaar`. |
| Merchant master | `merchant_id` | category, business type, location, status, ticket size | `settlement_account`. |

## Primary analytical fields

| Field | Meaning |
|---|---|
| `is_high_value_transaction` | Transaction amount at or above the transaction 95th percentile. |
| `is_user_amount_anomaly` | Transaction amount with absolute within-user z-score at least 2.5, where calculable. |
| `is_high_severity` | Chargeback severity is High or Critical. |
| `is_unauthorized_transaction` | Chargeback reason maps to Unauthorized Transaction. |
| `reporting_delay_hours` | Valid duration between transaction and chargeback reporting. |
| `transaction_record_found` | A chargeback `txn_id` links to an observed transaction. |
| `identity_mismatch` | A linked transaction differs from its chargeback user or merchant ID. |
| `network_disconnected` | Chargeback user–merchant pair is not in the observed transaction-pair network. |
| `chargeback_rate_min_volume` | Chargeback-records-per-transaction metric only when merchant transaction count is at least 5. |
| `risk_signal_count` | Count of documented signals; not a fraud score or label. |
| `risk_explanations` | Exact text reasons that contribute to an investigation candidate. |
| `investigation_priority` | `LOW`, `WATCH`, or `ELEVATED_REVIEW`, based only on the number of explainable signals. |
| `component_id`, `component_size`, `degree` | Calculated transaction-network graph properties. |

## Quality flags

Columns ending in `_parse_failure_flag`, `_invalid_flag`, `_unmapped_flag`, or `_before_transaction_flag` preserve cleaning and quality evidence. They do not alter the raw input or independently imply suspicious behavior.
