import json
import pandas as pd

INPUT_FILE = "data/raw/track1_chargebacks.json"

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

df = pd.DataFrame(data)

print("========== CHARGEBACK DATA AUDIT ==========")
print("Raw rows:", len(df))
print("Columns:", len(df.columns))

print("\n--- Missing values ---")
print(df.isna().sum())

print("\n--- Blank strings ---")
for col in df.columns:
    blanks = df[col].astype(str).str.strip().eq("").sum()
    if blanks > 0:
        print(f"{col}: {blanks}")

print("\n--- Duplicate rows ---")
print("Exact duplicate rows:", df.duplicated().sum())

print("\n--- Data types ---")
print(df.dtypes)

print("\n--- Unique values in categorical columns ---")
for col in ["reason_code", "resolution_status", "severity", "channel"]:
    print(f"\n{col}: {df[col].nunique()} unique values")
    print(sorted(df[col].dropna().astype(str).unique()))
# Remove exact duplicate records
# Remove exact duplicate records
before_dedup = len(df)

df = df.drop_duplicates().copy()

after_dedup = len(df)
duplicates_removed = before_dedup - after_dedup

print("\n--- Deduplication ---")
print("Rows before deduplication:", before_dedup)
print("Exact duplicates removed:", duplicates_removed)
print("Rows after deduplication:", after_dedup)
print("\n--- ID samples before standardization ---")

for col in ["txn_id", "user_id", "merchant_id"]:
    print(f"\n{col}:")
    print(df[col].drop_duplicates().head(10).tolist())
def standardize_id(value, prefix, digits):
    """
    Standardize IDs by removing separators/case differences
    and restoring the expected prefix and zero-padding.

    Blank values remain missing.
    """
    if pd.isna(value):
        return pd.NA

    value = str(value).strip()

    if value == "":
        return pd.NA

    # Keep only the numeric part
    numeric_part = "".join(ch for ch in value if ch.isdigit())

    if not numeric_part:
        return pd.NA

    # Keep only the expected number of digits
    numeric_part = numeric_part[-digits:]

    return f"{prefix}{numeric_part.zfill(digits)}"
df["txn_id"] = df["txn_id"].apply(
    standardize_id, prefix="TXN", digits=8
)

df["user_id"] = df["user_id"].apply(
    standardize_id, prefix="USR", digits=5
)

df["merchant_id"] = df["merchant_id"].apply(
    standardize_id, prefix="MCH", digits=4
)

print("\n--- ID standardization complete ---")
print("Missing txn_id:", df["txn_id"].isna().sum())
print("Missing user_id:", df["user_id"].isna().sum())
print("Missing merchant_id:", df["merchant_id"].isna().sum())
# Clean disputed amounts
df["disputed_amount"] = (
    df["disputed_amount"]
    .astype("string")
    .str.strip()
    .replace("", pd.NA)
)

# Convert currency-formatted values to numeric
df["disputed_amount"] = (
    df["disputed_amount"]
    .str.replace("₹", "", regex=False)
    .str.replace("Rs.", "", regex=False)
    .str.replace("INR", "", regex=False)
    .str.replace(",", "", regex=False)
    .str.strip()
)

df["disputed_amount"] = pd.to_numeric(
    df["disputed_amount"],
    errors="coerce"
)

# Flag invalid negative amounts
df["disputed_amount_invalid_flag"] = (
    df["disputed_amount"].lt(0).fillna(False)
)

# Negative monetary values are invalid
df.loc[
    df["disputed_amount_invalid_flag"],
    "disputed_amount"
] = pd.NA

print("\n--- Disputed amount cleaning ---")
print("Missing disputed amounts:", df["disputed_amount"].isna().sum())
print(
    "Invalid negative amounts:",
    df["disputed_amount_invalid_flag"].sum()
)
print(
    "Minimum valid disputed amount:",
    df["disputed_amount"].min()
)
# ---------------- TIMESTAMP CLEANING ----------------

def parse_timestamp(value):
    """
    Parse the mixed timestamp formats found in the dataset.
    Ambiguous numeric dates follow the dataset convention:
    - Slash format: DD/MM/YYYY
    - Hyphen format: MM-DD-YYYY
    """

    if pd.isna(value):
        return pd.NaT

    value = str(value).strip()

    if value == "":
        return pd.NaT

    # Unix timestamp (10-digit seconds)
    if value.isdigit() and len(value) == 10:
        return pd.to_datetime(
            int(value),
            unit="s",
            errors="coerce"
        )

    formats = [
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%Y/%m/%d %I:%M %p",
        "%d/%m/%Y %I:%M %p",

        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %I:%M %p",

        "%m-%d-%Y",
        "%m-%d-%Y %I:%M %p",
        "%m-%d-%Y %H:%M:%S",

        "%d-%b-%Y",
        "%d-%b-%Y %H:%M:%S",
        "%d-%b-%Y %I:%M %p",
    ]

    for fmt in formats:
        parsed = pd.to_datetime(
            value,
            format=fmt,
            errors="coerce"
        )

        if not pd.isna(parsed):
            return parsed

    return pd.NaT


for col in [
    "transaction_timestamp",
    "reported_timestamp",
    "bank_response_timestamp"
]:
    df[col] = df[col].apply(parse_timestamp)


print("\n--- Timestamp parsing ---")

for col in [
    "transaction_timestamp",
    "reported_timestamp",
    "bank_response_timestamp"
]:
    print(
        f"{col} missing after parsing:",
        df[col].isna().sum()
    )

# ---------------- TIMESTAMP VALIDATION ----------------

df["reported_before_transaction_flag"] = (
    df["reported_timestamp"].notna()
    & df["transaction_timestamp"].notna()
    & (df["reported_timestamp"] < df["transaction_timestamp"])
)

df["bank_response_before_transaction_flag"] = (
    df["bank_response_timestamp"].notna()
    & df["transaction_timestamp"].notna()
    & (df["bank_response_timestamp"] < df["transaction_timestamp"])
)

print("\n--- Timestamp validation ---")

print(
    "Reported before transaction:",
    df["reported_before_transaction_flag"].sum()
)

print(
    "Bank response before transaction:",
    df["bank_response_before_transaction_flag"].sum()
)
# Replace impossible timestamps with missing values
df.loc[
    df["reported_before_transaction_flag"],
    "reported_timestamp"
] = pd.NaT

df.loc[
    df["bank_response_before_transaction_flag"],
    "bank_response_timestamp"
] = pd.NaT

print("\n--- Impossible timestamps corrected ---")
print(
    "Reported timestamps set to missing:",
    df["reported_before_transaction_flag"].sum()
)
print(
    "Bank response timestamps set to missing:",
    df["bank_response_before_transaction_flag"].sum()
)
# ---------------- CATEGORICAL STANDARDIZATION ----------------

reason_map = {
    "charged twice": "DUPLICATE_DEBIT",
    "DUP_DEBIT": "DUPLICATE_DEBIT",
    "Duplicate Debit": "DUPLICATE_DEBIT",
    "double debit": "DUPLICATE_DEBIT",
    "dup debit": "DUPLICATE_DEBIT",

    "amount mismatch": "AMOUNT_MISMATCH",
    "Wrong Amount": "AMOUNT_MISMATCH",
    "extra amount deducted": "AMOUNT_MISMATCH",
    "incorrect amount": "AMOUNT_MISMATCH",

    "ATO": "ACCOUNT_TAKEOVER",
    "Account Takeover": "ACCOUNT_TAKEOVER",
    "account hacked": "ACCOUNT_TAKEOVER",
    "login compromised": "ACCOUNT_TAKEOVER",

    "Merchant Not Delivered": "SERVICE_NOT_PROVIDED",
    "Service Not Provided": "SERVICE_NOT_PROVIDED",
    "delivery issue": "SERVICE_NOT_PROVIDED",
    "item not received": "SERVICE_NOT_PROVIDED",
    "merchant service issue": "SERVICE_NOT_PROVIDED",
    "no service": "SERVICE_NOT_PROVIDED",
    "not delivered": "SERVICE_NOT_PROVIDED",
    "service failed": "SERVICE_NOT_PROVIDED",

    "Customer Dispute": "CUSTOMER_DISPUTE",
    "customer issue": "CUSTOMER_DISPUTE",
    "dispute raised": "CUSTOMER_DISPUTE",
    "complaint": "CUSTOMER_DISPUTE",

    "FRAUD": "UNAUTHORIZED_TRANSACTION",
    "Fraud Suspected": "UNAUTHORIZED_TRANSACTION",
    "fraud": "UNAUTHORIZED_TRANSACTION",
    "not done by me": "UNAUTHORIZED_TRANSACTION",
    "scam": "UNAUTHORIZED_TRANSACTION",
    "suspicious transaction": "UNAUTHORIZED_TRANSACTION",
    "unauth txn": "UNAUTHORIZED_TRANSACTION",
    "UNAUTHORISED": "UNAUTHORIZED_TRANSACTION",
    "Unauthorized Transaction": "UNAUTHORIZED_TRANSACTION",
    "unauthorized_transaction": "UNAUTHORIZED_TRANSACTION",
}


resolution_map = {
    "CLOSED": "CLOSED",
    "Closed": "CLOSED",
    "IN_PROGRESS": "IN_PROGRESS",
    "In Progress": "IN_PROGRESS",
    "WIP": "IN_PROGRESS",
    "OPEN": "OPEN",
    "Open": "OPEN",
    "PENDING_BANK": "PENDING_BANK",
    "Pending Bank": "PENDING_BANK",
    "REJECTED": "REJECTED",
    "Rejected": "REJECTED",
    "RESOLVED": "RESOLVED",
    "Resolved": "RESOLVED",
}


severity_map = {
    "CRIT": "CRITICAL",
    "Critical": "CRITICAL",
    "CRITICAL": "CRITICAL",
    "P1": "CRITICAL",

    "H": "HIGH",
    "High": "HIGH",
    "HIGH": "HIGH",
    "P2": "HIGH",

    "M": "MEDIUM",
    "Medium": "MEDIUM",
    "MEDIUM": "MEDIUM",
    "P3": "MEDIUM",

    "L": "LOW",
    "Low": "LOW",
    "LOW": "LOW",
    "P4": "LOW",
}


channel_map = {
    "App": "APP",
    "Branch": "BRANCH",
    "CHATBOT": "CHATBOT",
    "chatbot": "CHATBOT",
    "Call Center": "CALL_CENTER",
    "Email": "EMAIL",
    "IVR": "IVR",
    "ivr": "IVR",
}


# Apply mappings
df["reason_code"] = df["reason_code"].map(reason_map)
df["resolution_status"] = df["resolution_status"].map(resolution_map)
df["severity"] = df["severity"].map(severity_map)
df["channel"] = df["channel"].map(channel_map)


print("\n--- Categorical standardization ---")
print("Reason categories:", df["reason_code"].nunique())
print("Resolution statuses:", df["resolution_status"].nunique())
print("Severity levels:", df["severity"].nunique())
print("Channels:", df["channel"].nunique())

print("\nUnique reason categories:")
print(sorted(df["reason_code"].dropna().unique()))
# ---------------- FINAL VALIDATION ----------------

print("\n========== FINAL VALIDATION ==========")

print("Final row count:", len(df))
print("Duplicate rows remaining:", df.duplicated().sum())

print("\nMissing values:")
print(df.isna().sum())

print("\nInvalid disputed amounts:")
print(
    "Negative amounts remaining:",
    (df["disputed_amount"] < 0).sum()
)

print("\nCategorical nulls:")
for col in [
    "reason_code",
    "resolution_status",
    "severity",
    "channel"
]:
    print(f"{col}:", df[col].isna().sum())

print("\nTimestamp data types:")
for col in [
    "transaction_timestamp",
    "reported_timestamp",
    "bank_response_timestamp"
]:
    print(f"{col}:", df[col].dtype)
print("\n--- Amount flag validation ---")
print(
    "Rows flagged as invalid negative:",
    df["disputed_amount_invalid_flag"].sum()
)
print(
    "Rows with missing disputed amount:",
    df["disputed_amount"].isna().sum()
)
print(
    "Rows with missing disputed amount:",
    df["disputed_amount"].isna().sum()
)
# ---------------- EXPORT CLEANED DATA ----------------

OUTPUT_FILE = "data/processed/chargebacks_cleaned.csv"

df.to_csv(OUTPUT_FILE, index=False)

print("\n--- Export complete ---")
print("Cleaned dataset saved to:", OUTPUT_FILE)
print("Final rows exported:", len(df))
