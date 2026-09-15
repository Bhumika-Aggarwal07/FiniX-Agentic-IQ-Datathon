# FiniX architecture

## Layers

| Layer | Module / output | Responsibility |
|---|---|---|
| Ingestion | `src.finix.core.read_raw` | Read known source schemas without editing raw data. |
| Cleaning | `src.finix.cleaning` | Dataset-specific normalization, exact duplicate removal, type parsing, and audit records. |
| Validation | `src.finix.validation` | Report schema, missingness, duplicates, key uniqueness, and numeric integrity with numerator/denominator/percentage. |
| Features | `src.finix.analytics.engineer_features` | Derive date, status, amount, KYC, merchant, and chargeback features independently. |
| Integration | `src.finix.analytics.integrate` | Build safe summaries, link chargebacks by `txn_id`, and detect rather than correct mismatches. |
| Risk marts | `src.finix.analytics.build_risk_marts` | Create explainable user and merchant investigation candidates. |
| Network | `src.finix.network` | Calculate transaction bipartite graph components and relationship signals. |
| Dashboard | `app.py`, `app_pages/` | Present cached, dashboard-safe generated outputs. |
| Investigation | `src.finix.investigation` | Deterministic natural-language fallback over generated tables. |

## Cardinality controls

- `transactions.txn_id` must be unique after exact duplicate removal.
- KYC profiles are summarized to one user row before use as a lookup.
- Merchant master records are summarized to one merchant row before use as a lookup.
- Chargebacks join the transaction lookup as `many_to_one` by `txn_id`.
- Chargeback aggregates, not raw chargeback rows, join transactions as `one_to_one`.
- The pipeline raises an error if a linkage changes fact-table row count.

## Deployment

`app.py` is the Streamlit entry point. Paths are repository-relative. The dashboard uses `st.cache_data` for generated CSV loaders and the `.streamlit/config.toml` financial-security theme. No machine-specific paths or credentials appear in application code.
