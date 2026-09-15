# Integration and linkage policy

## Intended keys

| Relationship | Key | Treatment |
|---|---|---|
| Transaction → chargeback | `txn_id` | Chargebacks link to a unique transaction lookup as `many_to_one`. |
| Transaction → KYC | `user_id` | Repeated KYC records become one transparent user summary before join. |
| Transaction → merchant master | `merchant_id` | Repeated merchant records become one transparent merchant summary before join. |

## Linkage fields

`chargeback_linkage.csv` contains:

- `transaction_record_found` and `txn_id_match`
- `user_id_match`, `merchant_id_match`, and `user_merchant_pair_match`
- `network_disconnected`
- `disputed_amount_match`
- `identity_mismatch`, `data_quality_anomaly`, and `linkage_status`

`linkage_status` distinguishes `MISSING_TXN_ID`, `UNMATCHED_TRANSACTION`, `IDENTITY_MISMATCH`, `RELATIONSHIP_MISMATCH`, and `MATCHED_IDENTITIES`.

## Current integration finding

2,607 / 2,800 chargeback records link to a transaction by `txn_id` (93.11%). In this supplied data, every linked chargeback is an identity mismatch, and every chargeback user–merchant pair is absent from observed transaction pairs. FiniX retains both chargeback and transaction identity values and reports this as an integration signal. It never overwrites a chargeback identity and never turns a mismatch into a fraud label.

## Join safety

The pipeline validates source keys, uses Pandas merge cardinality validation, and checks fact-table row counts after each critical join. Unmatched chargebacks are retained; no unmatched rows are silently dropped.
