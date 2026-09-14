import pandas as pd

INPUT_FILE = "data/processed/chargebacks_cleaned.csv"

df = pd.read_csv(INPUT_FILE)

print("========== CHARGEBACK FEATURE ENGINEERING ==========")
print("Input rows:", len(df))
print("Input columns:", len(df.columns))


# Reporting delay: transaction to chargeback report
df["reporting_delay_hours"] = (
    pd.to_datetime(df["reported_timestamp"], errors="coerce")
    - pd.to_datetime(df["transaction_timestamp"], errors="coerce")
).dt.total_seconds() / 3600

print("\n--- Reporting delay ---")
print("Missing reporting delays:", df["reporting_delay_hours"].isna().sum())
print("Minimum delay (hours):", df["reporting_delay_hours"].min())
print("Maximum delay (hours):", df["reporting_delay_hours"].max())
print("Average delay (hours):", df["reporting_delay_hours"].mean())


# Bank response delay: chargeback report to bank response
df["bank_response_delay_hours"] = (
    pd.to_datetime(df["bank_response_timestamp"], errors="coerce")
    - pd.to_datetime(df["reported_timestamp"], errors="coerce")
).dt.total_seconds() / 3600

print("\n--- Bank response delay ---")
print("Missing bank response delays:", df["bank_response_delay_hours"].isna().sum())
print("Minimum delay (hours):", df["bank_response_delay_hours"].min())
print("Maximum delay (hours):", df["bank_response_delay_hours"].max())
print("Average delay (hours):", df["bank_response_delay_hours"].mean())

negative_bank_delays = (
    df["bank_response_delay_hours"] < 0
).sum()

print("Negative bank response delays:", negative_bank_delays)
# Data-quality flag: bank response before chargeback report
df["bank_response_before_report_flag"] = (
    df["bank_response_delay_hours"] < 0
)

print("\n--- Bank response validation ---")
print(
    "Bank responses before report:",
    df["bank_response_before_report_flag"].sum()
)
# Critical severity indicator
df["is_critical_dispute"] = (
    df["severity"] == "CRITICAL"
)

print("\n--- Critical dispute flag ---")
print(
    "Critical disputes:",
    df["is_critical_dispute"].sum()
)
# High severity indicator
df["is_high_severity"] = (
    df["severity"].isin(["CRITICAL", "HIGH"])
)

print("\n--- High severity flag ---")
print(
    "High severity disputes:",
    df["is_high_severity"].sum()
)
# Open case indicator
df["is_open_case"] = (
    df["resolution_status"].isin(["OPEN", "IN_PROGRESS", "PENDING_BANK"])
)

print("\n--- Open case flag ---")
print(
    "Open cases:",
    df["is_open_case"].sum()
)
# Account takeover indicator
df["is_account_takeover"] = (
    df["reason_code"] == "ACCOUNT_TAKEOVER"
)

print("\n--- Account takeover flag ---")
print(
    "Account takeover disputes:",
    df["is_account_takeover"].sum()
)
# Unauthorized transaction indicator
df["is_unauthorized_transaction"] = (
    df["reason_code"] == "UNAUTHORIZED_TRANSACTION"
)

print("\n--- Unauthorized transaction flag ---")
print(
    "Unauthorized transaction disputes:",
    df["is_unauthorized_transaction"].sum()
)
# High-value dispute indicator
high_value_threshold = df["disputed_amount"].quantile(0.75)

df["is_high_value_dispute"] = (
    df["disputed_amount"] >= high_value_threshold
)

print("\n--- High-value dispute flag ---")
print("High-value threshold:", high_value_threshold)
print(
    "High-value disputes:",
    df["is_high_value_dispute"].sum()
)
# Export feature-engineered dataset
OUTPUT_FILE = "data/processed/chargeback_features.csv"

df.to_csv(OUTPUT_FILE, index=False)

print("\n--- Export complete ---")
print("Feature dataset saved to:", OUTPUT_FILE)
print("Final rows exported:", len(df))