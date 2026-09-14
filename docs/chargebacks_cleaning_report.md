# Chargebacks — Data Cleaning Report

## Dataset

- Raw file: `data/raw/track1_chargebacks.json`
- Cleaned file: `data/processed/chargebacks_cleaned.csv`
- Feature file: `data/processed/chargeback_features.csv`
- Raw rows: 2,884
- Final cleaned rows: 2,800

---

## Cleaning Rules Applied

| Issue | Column(s) | Rule | Rows affected |
|---|---|---|---:|
| Exact duplicate records | All columns | Remove exact duplicate rows only | 84 |
| Inconsistent transaction IDs | `txn_id` | Standardize to `TXN` + 8 digits | Applicable records |
| Inconsistent user IDs | `user_id` | Standardize to `USR` + 5 digits | Applicable records |
| Inconsistent merchant IDs | `merchant_id` | Standardize to `MCH` + 4 digits | Applicable records |
| Currency symbols/commas in amounts | `disputed_amount` | Remove formatting characters and convert to numeric | Applicable records |
| Negative disputed amounts | `disputed_amount` | Treat as invalid and set to missing | 220 |
| Missing/invalid disputed amounts | `disputed_amount` | Preserve as missing; no values invented | 399 total issue cases |
| Mixed timestamp formats | Timestamp columns | Parse supported date/time formats into datetime | Applicable records |
| Reported before transaction | `reported_timestamp` | Flag and set impossible timestamp to missing | 92 |
| Bank response before transaction | `bank_response_timestamp` | Flag and set impossible timestamp to missing | 8 |
| Reason-code variation | `reason_code` | Map raw variants to canonical categories | 34 raw values → 6 |
| Resolution variation | `resolution_status` | Map raw variants to canonical categories | 13 raw values → 6 |
| Severity variation | `severity` | Map raw variants to canonical categories | 16 raw values → 4 |
| Channel variation | `channel` | Map raw variants to canonical categories | 8 raw values → 6 |
| Complaint text formatting | `complaint_text` | Trim surrounding whitespace | Applicable records |

---

## Validation After Cleaning

### Row count

- Raw rows: 2,884
- Exact duplicates removed: 84
- Final rows: 2,800

### Missing values after cleaning

- `txn_id`: 77
- `user_id`: 0
- `merchant_id`: 0
- `transaction_timestamp`: 230
- `reported_timestamp`: 295
- `disputed_amount`: 399
- `bank_response_timestamp`: 709
- Canonical categorical fields: 0 missing

### Invalid values

- Negative disputed amounts remaining: 0
- Overlong transaction IDs: 0
- Overlong user IDs: 0
- Overlong merchant IDs: 0
- Raw null-token occurrences (`NA`, `N/A`, `null`, `NULL`, `None`): 0

---

## Important Cleaning Decisions

### Exact duplicates

Only exact duplicate rows were removed.

Records were not deduplicated using `txn_id`, `user_id`, or `merchant_id`
because multiple complaints associated with an entity may represent
legitimate separate cases.

### Invalid amounts

Negative disputed amounts were treated as invalid and converted to missing.
The absolute value was not used because doing so would invent a positive
amount that was not present in the source data.

### Missing values

Missing values were preserved when they could not be reliably recovered.
No values were invented.

### Timestamps

Supported timestamp formats were converted into datetime values.

Impossible chronological relationships were flagged and the invalid
timestamp was set to missing rather than deleting the entire record.

Date-only values converted to midnight were retained, but they were not used
for behavioral hour-of-day analysis because doing so could create a
misleading midnight concentration.

### Identity fields

Chargeback `user_id` and `merchant_id` were standardized for formatting
only. They were not replaced using values from the Transactions table.

Cross-table identity inconsistencies were treated as integration findings,
not cleaning corrections.

---

## Feature Engineering

The cleaned dataset was extended with analytical features including:

- `reporting_delay_hours`
- `bank_response_delay_hours`
- `bank_response_before_report_flag`
- `is_critical_dispute`
- `is_high_severity`
- `is_open_case`
- `is_account_takeover`
- `is_unauthorized_transaction`
- `is_high_value_dispute`

The feature-engineered dataset contains 2,800 rows.

---

## Cross-Table Validation Findings

Chargebacks were linked to Transactions using `txn_id`.

The available data showed structural inconsistencies between Chargeback and
Transaction identity fields.

Observed findings include:

- Chargeback `user_id` did not match the linked Transaction `user_id`
  in the examined matched records.
- Chargeback `merchant_id` did not match the linked Transaction `merchant_id`
  in the examined matched records.
- Chargeback user–merchant pairs were not observed among Transaction
  user–merchant pairs in the comparison performed.
- Disputed amounts did not exactly match transaction amounts in records where
  both values were available.

These discrepancies were not automatically corrected because doing so could
overwrite potentially meaningful source information.

They will instead be used as integration and investigation signals.

---

## Reproducibility

The raw dataset is preserved under:

`data/raw/`

Cleaning is performed programmatically using:

`src/cleaning/chargebacks.py`

The cleaned dataset is written to:

`data/processed/chargebacks_cleaned.csv`

Feature engineering is performed using:

`src/analytics/chargeback_features.py`

The feature dataset is written to:

`data/processed/chargeback_features.csv`

EDA and analytical findings are documented in:

`notebooks/chargebacks_eda.ipynb`