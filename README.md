# FiniX — UPI Fraud Ring & Merchant Intelligence

> **From messy UPI data to explainable fraud investigations.**

FiniX is an end-to-end fraud analytics platform designed to help a National Payments Authority investigate **suspicious UPI activity, high-risk merchants, anomalous users, chargeback patterns, and potential fraud rings**.

Instead of treating fraud as a single suspicious transaction, FiniX combines **transaction behaviour + customer/KYC context + merchant behaviour + chargeback relationships + graph connectivity** to produce explainable investigation signals.

---

## 01 The Business Problem

UPI fraud is rarely visible from one row of data.

A suspicious case may look like:

```text
                    ┌─────────────┐
                    │    USER     │
                    └──────┬──────┘
                           │
                    many transactions
                           │
                           ▼
                    ┌─────────────┐
                    │  MERCHANT   │
                    └──────┬──────┘
                           │
                    repeated activity
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
       other users                chargebacks
              │                         │
              └────────────┬────────────┘
                           ▼
                    suspicious network
```

FiniX therefore asks:

* Which users show unusual transaction behaviour?
* Which merchants have abnormal transaction patterns?
* Which user–merchant relationships deserve investigation?
* Where are transaction and chargeback identities inconsistent?
* Which entities become suspicious when **multiple signals are considered together**?
* Are there connected components or transaction structures that may indicate coordinated fraud?
* Can an analyst ask these questions in natural language and receive the appropriate visualization?

---

# 02 Our Approach

FiniX follows a four-layer architecture aligned with the datathon:

```text
┌───────────────────────────────────────────────┐
│  LAYER 1 — DATA RESCUE                       │
│  Cleaning · Standardization · Validation      │
└──────────────────────┬────────────────────────┘
                       ▼
┌───────────────────────────────────────────────┐
│  LAYER 2 — ANALYTICS                          │
│  KPIs · Features · Relationships · Risk       │
└──────────────────────┬────────────────────────┘
                       ▼
┌───────────────────────────────────────────────┐
│  LAYER 3 — INVESTIGATION DASHBOARD            │
│  Interactive filters · KPIs · Graph · Cases   │
└──────────────────────┬────────────────────────┘
                       ▼
┌───────────────────────────────────────────────┐
│  LAYER 4 — AGENTIC GRAPH AI                   │
│  Ask → Understand → Query → Chart → Explain   │
└───────────────────────────────────────────────┘
```

---

# 03 Data Rescue

The supplied data is intentionally messy.

Our pipeline handles:

* Duplicate records
* Missing UTR values
* Missing MCC values
* Currency symbols embedded in amount fields
* Inconsistent timestamp formats
* Inconsistent transaction status values
* Whitespace and formatting inconsistencies
* Identifier formatting
* Cross-dataset relationship validation

### We follow one principle:

> **Standardize the representation without changing the underlying meaning.**

We do **not** blindly delete unusual observations.

For example, negative transaction amounts may be unusual, but removing them would potentially remove a fraud signal.

---

# 04 Transaction Data Rescue — Evidence

The raw UPI transaction dataset contains:

| Metric                      |     Result |
| --------------------------- | ---------: |
| Raw rows                    | **20,400** |
| Exact duplicate rows        |    **400** |
| Cleaned rows                | **20,000** |
| Missing UTR before cleaning |  **1,024** |
| Missing MCC before cleaning |  **2,926** |
| Missing UTR after cleaning  |  **1,000** |
| Missing MCC after cleaning  |  **2,872** |

The cleaning pipeline preserves the transaction-level grain and validates the output after transformation.

### Transaction amount formats

The raw data contains values such as:

```text
Rs. 6362.9
₹16,466.93
INR 13,312
```

These are converted into a consistent numeric representation without changing the underlying amount.

### Timestamp formats

The dataset contains multiple timestamp representations.

These are converted into a consistent datetime type and validated after parsing.

### Transaction status

Different representations of the same business state are standardized for analysis.

For example:

```text
SUCCESS
S
TXN_SUCCESS
COMPLETED
```

are treated as successful transaction variants for analytical grouping.

---

# 05 Transaction Insights

Our first-pass transaction analysis identified several investigation signals.

### Amount behaviour

Transaction amounts range from:

**−24,847.86 to 24,998.12**

with a median of approximately:

**12,218**

We retain unusual amounts instead of automatically treating them as errors.

### Negative transactions

After duplicate removal:

**420 transactions have negative amounts.**

These are treated as **investigation signals**, not automatic fraud classifications.

### Transaction status

After analytical grouping:

| Status group | Approx. share |
| ------------ | ------------: |
| Successful   |     **85.3%** |
| Failed       |      **9.8%** |
| Pending      |      **5.0%** |

No individual status category is treated as proof of fraud.

---

# 06 Feature Engineering

FiniX creates features at multiple levels.

### Transaction level

```text
amount
amount_abs
amount_percentile
amount_iqr_outlier_flag
negative_amount_flag
missing_utr_flag
missing_mcc_flag
status_group
txn_hour
txn_day_of_week
is_weekend
is_night
rapid_user_txn_flag
multiple_signal_flag
```

### User level

```text
user_transaction_count
user_total_amount
user_avg_amount
user_max_amount
user_min_amount
user_unique_merchants
user_negative_txn_count
user_missing_utr_count
user_missing_mcc_count
user_negative_txn_ratio
```

### Merchant level

```text
merchant_transaction_count
merchant_total_amount
merchant_avg_amount
merchant_max_amount
merchant_unique_users
merchant_negative_txn_count
merchant_missing_utr_count
merchant_missing_mcc_count
merchant_negative_txn_ratio
```

### Relationship level

```text
user_merchant_txn_count
user_merchant_total_amount
user_merchant_avg_amount
```

### Velocity

We calculate the time between consecutive transactions for the same user to identify unusually rapid activity.

---

# 07 From Tables to a Fraud Network

The core of FiniX is the transition from **row-level analysis to relationship-level investigation**.

Our primary data model is:

```text
                         ┌──────────────┐
                         │     KYC      │
                         └──────┬───────┘
                                │
                             user_id
                                │
                                ▼
                       ┌─────────────────┐
                       │  TRANSACTIONS   │
                       └────┬───────┬────┘
                            │       │
                      merchant_id  txn_id
                            │       │
                            ▼       ▼
                    ┌──────────┐ ┌─────────────┐
                    │ MERCHANT │ │ CHARGEBACKS │
                    └──────────┘ └─────────────┘
```

### Primary relationships

| Relationship             | Key           |
| ------------------------ | ------------- |
| Transaction → KYC        | `user_id`     |
| Transaction → Merchant   | `merchant_id` |
| Transaction → Chargeback | `txn_id`      |

---

# 08 Why We Don't Blindly Join the Data

One of the important discoveries during data rescue was that **not every identifier behaves like a clean foreign key**.

In particular, Chargeback `user_id` and `merchant_id` do not consistently correspond to the user and merchant attached to the linked transaction.

Instead of "fixing" these identifiers by assumption, FiniX preserves the discrepancy.

For a chargeback linked through `txn_id`, we can compare:

```text
Transaction user_id
        vs
Chargeback user_id
```

and:

```text
Transaction merchant_id
        vs
Chargeback merchant_id
```

This allows identity inconsistency itself to become an **investigation feature**.

> We preserve questionable relationships rather than silently rewriting them.

This is important because a bad join can manufacture a false fraud pattern.

---

# 09 Investigation Signals

FiniX combines multiple pieces of evidence.

Examples include:

```text
Negative amount
      +
Amount outlier
      +
Rapid transactions
      +
Night activity
      +
High user activity
      +
Unusual merchant connectivity
      +
Chargeback relationship
      +
Identity mismatch
      +
Graph structure
      ↓
Higher investigation priority
```

The system deliberately follows:

> **Anomaly ≠ Fraud**

A high-risk score means **"investigate this case"**, not **"this entity is guilty."**

---

# 10 Graph Analytics

The graph layer represents entities and relationships rather than isolated rows.

Potential graph entities:

```text
USER
MERCHANT
TRANSACTION
CHARGEBACK
```

Potential edges:

```text
USER ──transacted_with──> MERCHANT

USER ──created──> TRANSACTION

TRANSACTION ──belongs_to──> MERCHANT

TRANSACTION ──has_chargeback──> CHARGEBACK
```

Graph features can include:

* User degree
* Merchant degree
* Transaction frequency
* User–merchant edge frequency
* Connected components
* Network density
* Repeated paths
* Suspicious clusters
* Chargeback-linked nodes

This enables FiniX to move from:

> **"Which transaction looks strange?"**

to:

> **"Which connected group of entities deserves investigation?"**

---

# 11 Executive Dashboard

The dashboard is designed around an **investigator workflow**, rather than a collection of unrelated charts.

### Executive layer

Key KPIs:

```text
Total Transactions
Transaction Value
Successful Transactions
Failed Transactions
Pending Transactions
Suspicious Signals
Chargebacks
High-Risk Users
High-Risk Merchants
```

### Behaviour layer

Interactive analysis of:

* Transaction trends
* Amount distributions
* Status
* Time-of-day behaviour
* User activity
* Merchant activity

### Network layer

Interactive exploration of:

* User–merchant connections
* High-degree entities
* Suspicious components
* Chargeback-linked relationships

### Investigation layer

An analyst can drill into:

```text
User
  ↓
Transactions
  ↓
Merchants
  ↓
Chargebacks
  ↓
Risk signals
  ↓
Supporting evidence
```

---

# 12 Agentic Graph AI

### Ask it. Don't search for it.

The planned/implemented FiniX agent allows an analyst to ask questions in natural language.

Example:

> **"Which merchant category has the highest chargeback-to-transaction ratio this quarter?"**

The agent converts the question into:

```text
Natural Language
      ↓
Intent Detection
      ↓
Metric Selection
      ↓
Dataset / Feature Selection
      ↓
Aggregation
      ↓
Chart Selection
      ↓
Visualization
      ↓
Natural Language Explanation
```

For example:

```text
"Show transaction volume by merchant category over time"
                         ↓
                    LINE CHART
```

while:

```text
"Compare chargeback ratio across merchant categories"
                         ↓
                    BAR CHART
```

and:

```text
"Show transaction amount vs declared ticket size"
                         ↓
                  SCATTER PLOT
```

The agent is designed to satisfy all three bonus requirements:

1. **Understand natural-language questions**
2. **Select an appropriate visualization**
3. **Explain the result alongside the chart**

> **Important:** If the agent is not yet implemented in the submitted version, remove this section or mark it explicitly as `Planned`. Never claim a bonus feature that the evaluator cannot run.

---

# 13 Architecture

```text
                         ┌─────────────────┐
                         │     RAW DATA    │
                         └────────┬────────┘
                                  │
                                  ▼
                     ┌────────────────────────┐
                     │ Cleaning & Validation  │
                     │       Python/Pandas    │
                     └───────────┬────────────┘
                                 │
                                 ▼
                     ┌────────────────────────┐
                     │   Processed Datasets   │
                     └───────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
           KYC EDA          Merchant EDA      Transaction EDA
              │                  │                  │
              └──────────────────┼──────────────────┘
                                 ▼
                     ┌────────────────────────┐
                     │ Relationship Mapping   │
                     └───────────┬────────────┘
                                 ▼
                     ┌────────────────────────┐
                     │ Feature / Metric Layer │
                     └───────────┬────────────┘
                                 ▼
                     ┌────────────────────────┐
                     │     Graph Analytics    │
                     └───────────┬────────────┘
                                 ▼
                     ┌────────────────────────┐
                     │ Risk / Investigation   │
                     │        Layer            │
                     └───────────┬────────────┘
                                 ▼
               ┌─────────────────┴─────────────────┐
               ▼                                   ▼
      ┌──────────────────┐               ┌─────────────────┐
      │ Streamlit        │               │ Agentic Graph AI│
      │ Dashboard        │               │ Ask → Chart     │
      └──────────────────┘               └─────────────────┘
```

---

# 14 Project Structure

```text
FiniX/
│
├── README.md
├── requirements.txt
├── .gitignore
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── reports/
│
├── src/
│   ├── cleaning/
│   │   ├── transactions.py
│   │   ├── kyc.py
│   │   ├── merchants.py
│   │   └── chargebacks.py
│   │
│   ├── validation/
│   │   └── mapping.py
│   │
│   ├── analytics/
│   │   ├── features.py
│   │   ├── risk.py
│   │   └── graph.py
│   │
│   └── agent/
│
├── notebooks/
│   ├── 01_transactions_feature_engineering.ipynb
│   ├── 02_kyc_analysis.ipynb
│   ├── 03_merchant_analysis.ipynb
│   └── 04_chargeback_analysis.ipynb
│
├── docs/
│   ├── data_dictionary.csv
│   ├── cleaning_rules.md
│   └── schema.md
│
├── dashboard/
│   └── app.py
│
└── tests/
```

---

# 15 Reproducibility

## Requirements

* Python 3.x
* Pandas
* NumPy
* NetworkX
* Plotly
* Streamlit
* Jupyter

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run transaction cleaning

```bash
python src/cleaning/transactions.py
```

Output:

```text
data/processed/transactions_cleaned.csv
```

## Run transaction feature engineering

Open:

```text
notebooks/01_transactions_feature_engineering.ipynb
```

Run all cells.

Output:

```text
data/processed/transactions_features.csv
```

## Run relationship validation

```bash
python src/validation/mapping.py
```

## Run dashboard

```bash
streamlit run dashboard/app.py
```

---

# 16 Data Quality Philosophy

FiniX follows five principles:

### 1. Don't destroy information

Unusual values are investigated before removal.

### 2. Don't change meaning

Formatting is standardized, but business meaning is not guessed.

### 3. Don't blindly join tables

Relationships are validated before being used.

### 4. Preserve lineage

Raw → cleaned → features → analytics → dashboard.

### 5. Make every transformation reproducible

Cleaning is implemented as code rather than manual spreadsheet edits.

----

# 20 Why FiniX?

Traditional fraud dashboards often answer:

> **"What happened?"**

FiniX aims to answer:

> **"What happened, who is connected to it, why is it unusual, and where should an investigator look next?"**

The progression is:

```text
MESSY DATA
    ↓
TRUSTWORTHY DATA
    ↓
BEHAVIOURAL FEATURES
    ↓
RELATIONSHIPS
    ↓
GRAPH
    ↓
INVESTIGATION SIGNALS
    ↓
EXPLAINABLE INSIGHT
```




