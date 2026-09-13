"""Standalone cleaning pipeline for the merchant master dataset."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd


RAW_FILE = Path("data/raw/track1_merchants_master.csv")
OUTPUT_FILE = Path("data/processed/merchants_cleaned.csv")
REPORT_FILE = Path("data/processed/merchants_cleaning_report.csv")
MISSING_TOKENS = {"", "NA", "N/A", "NULL", "null", "None"}


def snake_case(name: object) -> str:
    """Convert a column name to lowercase snake_case."""
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(name).strip())
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def normalise_text(value: object) -> object:
    """Trim/collapse whitespace and apply the specified missing-value rules."""
    if pd.isna(value):
        return pd.NA
    text = re.sub(r"\s+", " ", str(value).strip())
    return pd.NA if text in MISSING_TOKENS else text


def standardise_merchant_id(value: object) -> object:
    if pd.isna(value):
        return pd.NA
    compact = re.sub(r"[^A-Za-z0-9]", "", str(value)).upper()
    if compact.startswith("MCH"):
        compact = compact[3:]
    return f"MCH{compact}" if compact else pd.NA


def currency_to_numeric(value: object) -> object:
    """Convert INR/Rs/currency-formatted ticket sizes to numeric values."""
    if pd.isna(value):
        return pd.NA
    text = re.sub(r"(?i)(INR|RS\.?)", "", str(value))
    text = re.sub(r"[^0-9.\-]", "", text.replace(",", ""))
    return pd.to_numeric(text, errors="coerce")


def parse_unambiguous_date(value: object) -> object:
    """Return NULL for ambiguous numeric dates rather than guessing their order."""
    if pd.isna(value):
        return pd.NaT
    text = str(value).strip()
    if re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{4}", text):
        first, second, _ = re.split(r"[/-]", text)
        if int(first) <= 12 and int(second) <= 12:
            return pd.NaT
        return pd.to_datetime(text, errors="coerce", dayfirst=int(first) > 12)
    return pd.to_datetime(text, errors="coerce", format="mixed")


def report_row(issue: str, column: str, rule: str, affected: int,
               before: int, after: int) -> dict[str, object]:
    return {"Issue": issue, "Column": column, "Rule_Applied": rule,
            "Rows_Affected": int(affected), "Before_Count": int(before),
            "After_Count": int(after)}


def clean_merchants_dataset(input_path: Path = RAW_FILE,
                            output_path: Path = OUTPUT_FILE,
                            report_path: Path = REPORT_FILE) -> dict[str, object]:
    """Clean merchant data only; this function never joins or merges datasets."""
    if not input_path.exists():
        raise FileNotFoundError(f"Raw merchant file not found: {input_path.resolve()}")

    df = pd.read_csv(input_path, dtype=str, keep_default_na=False)
    df.columns = [snake_case(column) for column in df.columns]
    df = df.map(normalise_text)
    raw_rows = len(df)
    duplicate_count = int(df.duplicated(keep="first").sum())
    df = df.drop_duplicates(keep="first").copy()  # Only exact source-row duplicates.
    report = [report_row("Exact duplicate rows", "ALL", "Remove exact duplicate rows only",
                         duplicate_count, raw_rows, len(df))]

    if "merchant_id" in df:
        original = df["merchant_id"].copy()
        df["merchant_id"] = df["merchant_id"].map(standardise_merchant_id)
        report.append(report_row("ID standardisation", "merchant_id",
                                 "Canonical MCH + alphanumeric body",
                                 int((original != df["merchant_id"]).fillna(False).sum()),
                                 raw_rows, len(df)))

    if "mcc" in df:
        # A trailing .0 is a common CSV numeric-export artefact, not part of an MCC.
        df["mcc"] = df["mcc"].map(
            lambda x: pd.NA if pd.isna(x) else re.sub(r"\.0$", "", re.sub(r"[^0-9.]", "", str(x)))
        )
        df["mcc_valid"] = df["mcc"].map(
            lambda x: bool(re.fullmatch(r"\d{4}", str(x))) if pd.notna(x) else False
        )
        invalid_mcc = int((df["mcc"].notna() & ~df["mcc_valid"]).sum())
        report.append(report_row("MCC validation", "mcc",
                                 "Digits only; preserve leading zeros; exactly four digits",
                                 invalid_mcc, len(df), len(df) - invalid_mcc))

    for column in ("merchant_category", "business_type", "merchant_status", "city", "state"):
        if column in df:
            df[column] = df[column].str.upper()

    if "settlement_account" in df:
        df["settlement_account"] = df["settlement_account"].map(
            lambda x: pd.NA if pd.isna(x) else re.sub(r"[^A-Za-z0-9]", "", str(x)).upper()
        )
        df["settlement_account_valid"] = df["settlement_account"].map(
            lambda x: bool(re.fullmatch(r"[A-Z0-9]{9,18}", str(x))) if pd.notna(x) else False
        )
        invalid_account = int((df["settlement_account"].notna() & ~df["settlement_account_valid"]).sum())
        report.append(report_row("Settlement account validation", "settlement_account",
                                 "Alphanumeric account, 9-18 characters",
                                 invalid_account, len(df), len(df) - invalid_account))

    if "declared_avg_ticket_size" in df:
        present_before = int(df["declared_avg_ticket_size"].notna().sum())
        df["declared_avg_ticket_size"] = df["declared_avg_ticket_size"].map(currency_to_numeric)
        present_after = int(df["declared_avg_ticket_size"].notna().sum())
        report.append(report_row("Ticket size conversion", "declared_avg_ticket_size",
                                 "Remove currency formatting; convert numeric",
                                 present_before - present_after, present_before, present_after))

    date_failures = 0
    if "onboarding_date" in df:
        original_dates = df["onboarding_date"]
        parsed_dates = original_dates.map(parse_unambiguous_date)
        date_failures = int((original_dates.notna() & parsed_dates.isna()).sum())
        df["onboarding_date"] = parsed_dates.dt.strftime("%Y-%m-%d").astype("string")
        report.append(report_row("Date parsing", "onboarding_date",
                                 "Only unambiguous valid dates to YYYY-MM-DD",
                                 date_failures, len(df), len(df) - date_failures))

    missing = df.isna().sum()
    for column, count in missing.items():
        report.append(report_row("Missing values", column,
                                 "Specified missing tokens converted to NULL",
                                 int(count), len(df), len(df) - int(count)))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    pd.DataFrame(report).to_csv(report_path, index=False)
    return {"raw_rows": raw_rows, "cleaned_rows": len(df),
            "duplicates_removed": duplicate_count, "invalid_mcc": invalid_mcc,
            "invalid_settlement_accounts": invalid_account,
            "date_parsing_failures": date_failures, "missing_values": missing.to_dict()}


def main() -> None:
    try:
        summary = clean_merchants_dataset()
    except (FileNotFoundError, pd.errors.ParserError, OSError) as error:
        print(f"Merchant cleaning failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    print("Merchant dataset cleaning completed")
    for label, value in summary.items():
        print(f"{label.replace('_', ' ').title()}: {value}")


if __name__ == "__main__":
    main()
