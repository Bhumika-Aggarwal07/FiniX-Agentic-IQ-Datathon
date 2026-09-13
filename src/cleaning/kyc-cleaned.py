"""Independent, reproducible cleaning pipelines for the AgentIQ FinTech track.

Raw input is read only.  The two pipelines deliberately never merge or join data.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Callable

import pandas as pd


RAW_DIR = Path("data/raw")
OUTPUT_DIR = Path("data/processed")
MISSING_TOKENS = {"", "NA", "N/A", "NULL", "null", "None"}
PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


def snake_case(name: object) -> str:
    """Return a predictable lowercase snake_case column name."""
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(name).strip())
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def normalise_text(value: object) -> object:
    """Trim and collapse whitespace, and convert the specified null markers."""
    if pd.isna(value):
        return pd.NA
    value = re.sub(r"\s+", " ", str(value).strip())
    return pd.NA if value in MISSING_TOKENS else value


def load_raw_csv(path: Path) -> pd.DataFrame:
    """Read values as strings so identifier leading zeroes cannot be lost."""
    if not path.exists():
        raise FileNotFoundError(f"Raw file not found: {path.resolve()}")
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    frame.columns = [snake_case(column) for column in frame.columns]
    return frame.map(normalise_text)


def standardise_prefixed_id(value: object, prefix: str) -> object:
    if pd.isna(value):
        return pd.NA
    # Preserve the identifier body while accepting common separators and casing.
    compact = re.sub(r"[^A-Za-z0-9]", "", str(value)).upper()
    compact = compact[len(prefix):] if compact.startswith(prefix) else compact
    return f"{prefix}{compact}" if compact else pd.NA


def money_to_number(value: object) -> object:
    """Extract a decimal currency amount without coercing malformed values to zero."""
    if pd.isna(value):
        return pd.NA
    cleaned = re.sub(r"(?i)(INR|RS\.?)", "", str(value))
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned.replace(",", ""))
    return pd.to_numeric(cleaned, errors="coerce")


def parse_unambiguous_date(value: object) -> object:
    """Parse ISO and unambiguous day/month strings; ambiguous numeric dates are NULL."""
    if pd.isna(value):
        return pd.NaT
    text = str(value).strip()
    if re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{4}", text):
        first, second, _ = re.split(r"[/-]", text)
        # 10/01/2026 may mean either date, so it is intentionally not guessed.
        if int(first) <= 12 and int(second) <= 12:
            return pd.NaT
        return pd.to_datetime(text, errors="coerce", dayfirst=int(first) > 12)
    # ``mixed`` accepts the heterogeneous timestamp formats present in KYC data
    # without emitting format-inference warnings.
    return pd.to_datetime(text, errors="coerce", format="mixed")


def format_dates(series: pd.Series) -> tuple[pd.Series, int]:
    parsed = series.map(parse_unambiguous_date)
    failures = int((series.notna() & parsed.isna()).sum())
    return parsed.dt.strftime("%Y-%m-%d").astype("string"), failures


def report_row(issue: str, column: str, rule: str, affected: int,
               before: int, after: int) -> dict[str, object]:
    return {"Issue": issue, "Column": column, "Rule_Applied": rule,
            "Rows_Affected": int(affected), "Before_Count": int(before),
            "After_Count": int(after)}


def remove_exact_duplicates(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Drop only rows identical in the original, pre-cleaned source representation."""
    duplicates = int(frame.duplicated(keep="first").sum())
    return frame.drop_duplicates(keep="first").copy(), duplicates


def clean_kyc_dataset(input_path: Path, output_path: Path,
                      report_path: Path) -> dict[str, object]:
    """Clean KYC data independently and write its data and audit report."""
    raw = load_raw_csv(input_path)
    raw_rows = len(raw)
    df, duplicate_count = remove_exact_duplicates(raw)
    report: list[dict[str, object]] = [report_row(
        "Exact duplicate rows", "ALL", "Remove exact duplicate rows only",
        duplicate_count, raw_rows, len(df))]

    for col in ["user_id", "pan", "aadhaar", "monthly_income", "city", "state",
                "kyc_status", "risk_segment", "signup_date", "signup_timestamp"]:
        if col not in df.columns:
            continue
        before_missing = int(df[col].isna().sum())
        if col == "user_id":
            before = df[col].copy()
            df[col] = df[col].map(lambda x: standardise_prefixed_id(x, "USR"))
            report.append(report_row("ID standardisation", col, "Canonical USR + alphanumeric body",
                                     int((before != df[col]).fillna(False).sum()), before_missing, int(df[col].isna().sum())))

    if "pan" in df:
        df["pan"] = df["pan"].map(lambda x: pd.NA if pd.isna(x) else re.sub(r"[ -]", "", str(x)).upper())
        df["pan_valid"] = df["pan"].map(lambda x: bool(PAN_PATTERN.fullmatch(str(x))) if pd.notna(x) else False)
        invalid = int((df["pan"].notna() & ~df["pan_valid"]).sum())
        report.append(report_row("PAN validation", "pan", "Uppercase; remove spaces/hyphens; PAN regex", invalid, len(df), len(df) - invalid))
    if "aadhaar" in df:
        df["aadhaar"] = df["aadhaar"].map(lambda x: pd.NA if pd.isna(x) else re.sub(r"\D", "", str(x)))
        df["aadhaar_valid"] = df["aadhaar"].map(lambda x: bool(re.fullmatch(r"\d{12}", str(x))) if pd.notna(x) else False)
        invalid = int((df["aadhaar"].notna() & ~df["aadhaar_valid"]).sum())
        report.append(report_row("Aadhaar validation", "aadhaar", "Digits only; exactly 12 digits", invalid, len(df), len(df) - invalid))
    if "monthly_income" in df:
        before = df["monthly_income"].notna().sum()
        df["monthly_income"] = df["monthly_income"].map(money_to_number)
        report.append(report_row("Income conversion", "monthly_income", "Remove currency formatting; convert numeric", int(before - df["monthly_income"].notna().sum()), int(before), int(df["monthly_income"].notna().sum())))
    for col in ("city", "state", "kyc_status", "risk_segment"):
        if col in df:
            df[col] = df[col].str.upper()
    date_col = "signup_date" if "signup_date" in df else "signup_timestamp" if "signup_timestamp" in df else None
    date_failures = 0
    if date_col:
        df[date_col], date_failures = format_dates(df[date_col])
        report.append(report_row("Date parsing", date_col, "Parse valid dates to YYYY-MM-DD", date_failures, len(df), len(df) - date_failures))

    missing = df.isna().sum()
    for col, count in missing.items():
        report.append(report_row("Missing values", col, "Specified missing tokens converted to NULL", count, len(df), len(df) - count))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    pd.DataFrame(report).to_csv(report_path, index=False)
    return {"raw": raw_rows, "cleaned": len(df), "duplicates": duplicate_count, "missing": missing.to_dict(), "invalid_pan": int((df["pan"].notna() & ~df["pan_valid"]).sum()) if "pan" in df else 0, "invalid_aadhaar": int((df["aadhaar"].notna() & ~df["aadhaar_valid"]).sum()) if "aadhaar" in df else 0, "date_failures": date_failures}


def clean_merchants_dataset(input_path: Path, output_path: Path,
                            report_path: Path) -> dict[str, object]:
    """Clean merchant master data independently and write its data and audit report."""
    raw = load_raw_csv(input_path)
    raw_rows = len(raw)
    df, duplicate_count = remove_exact_duplicates(raw)
    report = [report_row("Exact duplicate rows", "ALL", "Remove exact duplicate rows only", duplicate_count, raw_rows, len(df))]
    if "merchant_id" in df:
        before = df["merchant_id"].copy()
        df["merchant_id"] = df["merchant_id"].map(lambda x: standardise_prefixed_id(x, "MCH"))
        report.append(report_row("ID standardisation", "merchant_id", "Canonical MCH + alphanumeric body", int((before != df["merchant_id"]).fillna(False).sum()), raw_rows, len(df)))
    if "mcc" in df:
        df["mcc"] = df["mcc"].map(lambda x: pd.NA if pd.isna(x) else re.sub(r"\.0$", "", re.sub(r"[^0-9.]", "", str(x))))
        df["mcc_valid"] = df["mcc"].map(lambda x: bool(re.fullmatch(r"\d{4}", str(x))) if pd.notna(x) else False)
        invalid_mcc = int((df["mcc"].notna() & ~df["mcc_valid"]).sum())
        report.append(report_row("MCC validation", "mcc", "Digits only; preserve zeros; exactly four digits", invalid_mcc, len(df), len(df) - invalid_mcc))
    for col in ("merchant_category", "business_type", "merchant_status", "city", "state"):
        if col in df:
            df[col] = df[col].str.upper()
    if "settlement_account" in df:
        df["settlement_account"] = df["settlement_account"].map(lambda x: pd.NA if pd.isna(x) else re.sub(r"[^A-Za-z0-9]", "", str(x)).upper())
        df["settlement_account_valid"] = df["settlement_account"].map(lambda x: bool(re.fullmatch(r"[A-Z0-9]{9,18}", str(x))) if pd.notna(x) else False)
        invalid_account = int((df["settlement_account"].notna() & ~df["settlement_account_valid"]).sum())
        report.append(report_row("Settlement account validation", "settlement_account", "Alphanumeric account, 9-18 characters", invalid_account, len(df), len(df) - invalid_account))
    if "declared_avg_ticket_size" in df:
        before = df["declared_avg_ticket_size"].notna().sum()
        df["declared_avg_ticket_size"] = df["declared_avg_ticket_size"].map(money_to_number)
        report.append(report_row("Ticket size conversion", "declared_avg_ticket_size", "Remove currency formatting; convert numeric", int(before - df["declared_avg_ticket_size"].notna().sum()), int(before), int(df["declared_avg_ticket_size"].notna().sum())))
    date_failures = 0
    if "onboarding_date" in df:
        df["onboarding_date"], date_failures = format_dates(df["onboarding_date"])
        report.append(report_row("Date parsing", "onboarding_date", "Only unambiguous valid dates to YYYY-MM-DD", date_failures, len(df), len(df) - date_failures))
    missing = df.isna().sum()
    for col, count in missing.items():
        report.append(report_row("Missing values", col, "Specified missing tokens converted to NULL", count, len(df), len(df) - count))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    pd.DataFrame(report).to_csv(report_path, index=False)
    return {"raw": raw_rows, "cleaned": len(df), "duplicates": duplicate_count, "missing": missing.to_dict(), "invalid_mcc": int((df["mcc"].notna() & ~df["mcc_valid"]).sum()) if "mcc" in df else 0, "invalid_account": int((df["settlement_account"].notna() & ~df["settlement_account_valid"]).sum()) if "settlement_account" in df else 0, "date_failures": date_failures}


def print_summary(name: str, summary: dict[str, object]) -> None:
    print(f"\n{name} dataset")
    print(f"Raw row count: {summary['raw']}\nCleaned row count: {summary['cleaned']}\nDuplicate rows removed: {summary['duplicates']}")
    print(f"Missing values per column: {summary['missing']}")
    for key in ("invalid_pan", "invalid_aadhaar", "invalid_mcc", "invalid_account", "date_failures"):
        if key in summary:
            print(f"{key.replace('_', ' ').title()}: {summary[key]}")


def main() -> None:
    try:
        kyc = clean_kyc_dataset(RAW_DIR / "track1_kyc_records.csv", OUTPUT_DIR / "kyc_cleaned.csv", OUTPUT_DIR / "kyc_cleaning_report.csv")
        merchants = clean_merchants_dataset(RAW_DIR / "track1_merchants_master.csv", OUTPUT_DIR / "merchants_cleaned.csv", OUTPUT_DIR / "merchants_cleaning_report.csv")
        print_summary("KYC", kyc)
        print_summary("Merchant", merchants)
    except (FileNotFoundError, pd.errors.ParserError, OSError) as exc:
        print(f"Cleaning failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
