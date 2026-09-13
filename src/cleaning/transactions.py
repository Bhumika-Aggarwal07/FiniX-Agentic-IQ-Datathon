import re
from pathlib import Path

import pandas as pd


# ============================================================
# 1. FILE PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_FILE = PROJECT_ROOT / "data" / "raw" / "track1_upi_transactions.csv"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "transactions_cleaned.csv"


# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def clean_column_name(column):
    """Convert column names to lowercase snake_case."""
    column = str(column).strip().lower()
    column = re.sub(r"[^a-z0-9]+", "_", column)
    return column.strip("_")


def clean_text(value):
    """Standardize whitespace while preserving missing values."""
    if pd.isna(value):
        return pd.NA

    value = str(value).strip()
    value = re.sub(r"\s+", " ", value)

    return value if value else pd.NA


def parse_timestamp(value):
    """Parse supported timestamp formats, including Unix seconds."""

    if pd.isna(value):
        return pd.NaT

    value = str(value).strip()

    # Unix timestamp
    if value.isdigit() and len(value) >= 9:
        try:
            return pd.to_datetime(
                int(value),
                unit="s",
                errors="coerce"
            )
        except (ValueError, TypeError, OverflowError):
            return pd.NaT

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
        "%m-%d-%Y %I:%M:%S %p",
        "%d-%m-%Y %I:%M:%S %p",
    ]

    for fmt in formats:
        try:
            return pd.to_datetime(value, format=fmt)
        except (ValueError, TypeError):
            continue

    return pd.NaT


def clean_amount(series):
    """Remove currency formatting and convert amounts to numeric."""

    return pd.to_numeric(
        series
        .astype("string")
        .str.replace(r"(?i)\bINR\b", "", regex=True)
        .str.replace(r"(?i)\bRs\.?\b", "", regex=True)
        .str.replace("₹", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip(),
        errors="coerce"
    )


# ============================================================
# 3. LOAD RAW DATA
# ============================================================

if not RAW_FILE.exists():
    raise FileNotFoundError(
        f"Raw transaction file not found:\n{RAW_FILE}"
    )

df = pd.read_csv(RAW_FILE, dtype="string")

raw_rows = len(df)
raw_columns = len(df.columns)

print("=" * 60)
print("TRANSACTIONS DATA AUDIT")
print("=" * 60)

print(f"Raw rows    : {raw_rows}")
print(f"Raw columns : {raw_columns}")


# ============================================================
# 4. STANDARDIZE COLUMN NAMES
# ============================================================

df.columns = [clean_column_name(col) for col in df.columns]

print("\nColumn names:")
print(df.columns.tolist())


# ============================================================
# 5. STANDARDIZE WHITESPACE
# ============================================================

for col in df.columns:
    df[col] = df[col].map(clean_text)


# ============================================================
# 6. STANDARDIZE MISSING VALUES
# ============================================================

missing_values = {
    "",
    "NA",
    "N/A",
    "null",
    "NULL",
    "None",
}

for col in df.columns:
    df[col] = df[col].replace(list(missing_values), pd.NA)

print("\nMissing values BEFORE cleaning:")
print(df.isna().sum())


# ============================================================
# 7. REMOVE ONLY EXACT DUPLICATES
# ============================================================

duplicate_count = int(df.duplicated().sum())

print(f"\nExact duplicate rows found: {duplicate_count}")

df = df.drop_duplicates().reset_index(drop=True)

print(f"Rows after duplicate removal: {len(df)}")


# ============================================================
# 8. IDs → STRING
# ============================================================

id_columns = [
    "txn_id",
    "user_id",
    "merchant_id",
    "utr",
]

for col in id_columns:
    if col in df.columns:
        df[col] = df[col].astype("string").str.strip()


# ============================================================
# 9. STATUS → STANDARD FORMAT
# ============================================================

if "status" in df.columns:
    df["status"] = (
        df["status"]
        .astype("string")
        .str.strip()
        .str.upper()
    )


# ============================================================
# 10. CLEAN AMOUNT
# ============================================================

if "amount" in df.columns:
    df["amount"] = clean_amount(df["amount"])


# ============================================================
# 11. TIMESTAMP → DATETIME
# ============================================================

if "timestamp" in df.columns:
    df["timestamp"] = df["timestamp"].apply(parse_timestamp)

timestamp_missing = int(df["timestamp"].isna().sum())

print("\nMissing timestamps after conversion:")
print(timestamp_missing)


# ============================================================
# 12. MCC
# ============================================================

if "mcc" in df.columns:
    df["mcc"] = (
        df["mcc"]
        .astype("string")
        .str.strip()
    )


# ============================================================
# 13. FINAL VALIDATION / AUDIT
# ============================================================

print("\n" + "=" * 60)
print("CLEANED DATA AUDIT")
print("=" * 60)

print(f"Cleaned rows    : {len(df)}")
print(f"Cleaned columns : {len(df.columns)}")

print("\nMissing values AFTER cleaning:")
print(df.isna().sum())

print("\nData types:")
print(df.dtypes)

print("\nRemaining exact duplicates:")
print(int(df.duplicated().sum()))

if "txn_id" in df.columns:
    print("\nUnique transaction IDs:")
    print(df["txn_id"].nunique())

if "amount" in df.columns:
    print("\nAmount summary:")
    print(df["amount"].describe())

    negative_count = int((df["amount"] < 0).sum())
    print("\nNegative transaction amounts:")
    print(negative_count)

if "status" in df.columns:
    print("\nStatus values:")
    print(df["status"].value_counts(dropna=False))


# ============================================================
# 14. SAVE CLEANED DATA
# ============================================================

OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)

df.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\n" + "=" * 60)
print("CLEANING COMPLETE")
print("=" * 60)

print(f"Saved cleaned file to:")
print(OUTPUT_FILE)