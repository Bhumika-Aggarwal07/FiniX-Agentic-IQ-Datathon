# Chargebacks — Data Dictionary

| Column | Description | Data Type | Cleaning / Standardization |
|---|---|---|---|
| `complaint_id` | Unique identifier for the chargeback complaint | String | Standardized as a string; source format retained |
| `txn_id` | Transaction identifier associated with the complaint | String | Standardized to `TXN` + 8 digits; missing values preserved |
| `user_id` | User identifier associated with the complaint | String | Standardized to `USR` + 5 digits |
| `merchant_id` | Merchant identifier associated with the complaint | String | Standardized to `MCH` + 4 digits |
| `transaction_timestamp` | Timestamp of the original transaction | Datetime | Mixed source formats parsed into datetime; invalid/impossible values handled as missing |
| `reported_timestamp` | Timestamp when the chargeback was reported | Datetime | Mixed formats parsed into datetime; impossible pre-transaction timestamps handled as missing |
| `disputed_amount` | Amount disputed in the chargeback | Numeric | Currency symbols, commas and spaces removed; invalid negative values treated as missing |
| `reason_code` | Reason associated with the chargeback | String / Categorical | Raw variants standardized into 6 canonical categories |
| `complaint_text` | Text describing the customer's complaint | String | Text retained; surrounding whitespace trimmed |
| `resolution_status` | Current resolution state of the chargeback | String / Categorical | Raw variants standardized into 6 canonical statuses |
| `bank_response_timestamp` | Timestamp of the bank's response | Datetime | Mixed formats parsed into datetime; impossible pre-transaction timestamps handled as missing |
| `severity` | Severity classification of the chargeback | String / Categorical | Raw variants standardized into 4 canonical levels |
| `channel` | Channel through which the complaint was submitted | String / Categorical | Raw variants standardized into 6 canonical channels |
| `disputed_amount_invalid_flag` | Indicates whether the original disputed amount was identified as invalid | Boolean | `True` for invalid negative amounts; otherwise `False` |
| `reported_before_transaction_flag` | Indicates whether the reported timestamp occurred before the transaction timestamp | Boolean | `True` for impossible chronological relationship; otherwise `False` |
| `bank_response_before_transaction_flag` | Indicates whether the bank response occurred before the transaction timestamp | Boolean | `True` for impossible chronological relationship; otherwise `False` |
| `reporting_delay_hours` | Time between transaction and chargeback reporting | Numeric | Calculated in hours from valid timestamps |
| `bank_response_delay_hours` | Time between transaction and bank response | Numeric | Calculated in hours from valid timestamps |
| `bank_response_before_report_flag` | Indicates whether the bank response occurred before the chargeback was reported | Boolean | `True` when bank response precedes reporting timestamp |
| `is_critical_dispute` | Indicates whether the chargeback has Critical severity | Boolean | Derived from `severity` |
| `is_high_severity` | Indicates whether the chargeback has High or Critical severity | Boolean | Derived from `severity` |
| `is_open_case` | Indicates whether the case is Open, In Progress, or Pending Bank | Boolean | Derived from `resolution_status` |
| `is_account_takeover` | Indicates whether the reason is Account Takeover | Boolean | Derived from `reason_code` |
| `is_unauthorized_transaction` | Indicates whether the reason is Unauthorized Transaction | Boolean | Derived from `reason_code` |
| `is_high_value_dispute` | Indicates whether the disputed amount is at or above the 75th percentile | Boolean | Threshold calculated from valid disputed amounts |

## Canonical Categories

### Reason Code

The raw reason-code variants were standardized into:

- `DUPLICATE_DEBIT`
- `AMOUNT_MISMATCH`
- `ACCOUNT_TAKEOVER`
- `SERVICE_NOT_PROVIDED`
- `CUSTOMER_DISPUTE`
- `UNAUTHORIZED_TRANSACTION`

### Resolution Status

The raw resolution-status variants were standardized into:

- `CLOSED`
- `OPEN`
- `IN_PROGRESS`
- `PENDING_BANK`
- `RESOLVED`
- `REJECTED`

### Severity

The raw severity variants were standardized into:

- `CRITICAL`
- `HIGH`
- `MEDIUM`
- `LOW`

### Channel

The raw channel variants were standardized into:

- `APP`
- `BRANCH`
- `CALL_CENTER`
- `CHATBOT`
- `EMAIL`
- `IVR`

## Notes

- Raw data is preserved and is not modified.
- Exact duplicates are removed only when the complete rows are identical.
- IDs are standardized for formatting without changing the underlying identity.
- Missing values are not artificially filled.
- Cross-table identity mismatches are treated as integration findings rather than cleaning corrections.