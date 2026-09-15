"""Shared, deterministic utilities for the FiniX pipeline.

Raw data is read only.  Every cleaned output is derived from paths relative to
the repository root so the project can run on a new machine without edits.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORTS_DIR = PROJECT_ROOT / "data" / "reports"

MISSING_TOKENS = {"", "NA", "N/A", "NULL", "NONE", "NAN", "<NA>"}

RAW_FILES = {
    "transactions": RAW_DIR / "track1_upi_transactions.csv",
    "kyc": RAW_DIR / "track1_kyc_records.csv",
    "merchants": RAW_DIR / "track1_merchants_master.csv",
    "chargebacks": RAW_DIR / "track1_chargebacks.json",
}

REQUIRED_COLUMNS = {
    "transactions": {
        "txn_id", "timestamp", "user_id", "merchant_id", "amount", "utr", "mcc", "status"
    },
    "kyc": {
        "user_id", "full_name", "pan", "aadhaar", "date_of_birth", "city", "state",
        "monthly_income", "occupation", "signup_timestamp", "kyc_status", "risk_segment",
    },
    "merchants": {
        "merchant_id", "merchant_name", "mcc", "merchant_category", "business_type", "city",
        "state", "onboarding_date", "settlement_account", "merchant_status",
        "declared_avg_ticket_size",
    },
    "chargebacks": {
        "complaint_id", "txn_id", "user_id", "merchant_id", "transaction_timestamp",
        "reported_timestamp", "disputed_amount", "reason_code", "complaint_text",
        "resolution_status", "bank_response_timestamp", "severity", "channel",
    },
}


def snake_case(value: object) -> str:
    """Return stable lowercase snake-case names for source headers."""
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value).strip())
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def read_raw(dataset: str) -> pd.DataFrame:
    """Read one known raw dataset without changing it."""
    path = RAW_FILES[dataset]
    if not path.is_file():
        raise FileNotFoundError(f"Required raw dataset is missing: {path}")
    if path.suffix.lower() == ".json":
        with path.open(encoding="utf-8") as handle:
            frame = pd.DataFrame(json.load(handle))
    else:
        frame = pd.read_csv(path, dtype="string", keep_default_na=False)
    frame.columns = [snake_case(column) for column in frame.columns]
    missing = REQUIRED_COLUMNS[dataset] - set(frame.columns)
    if missing:
        raise ValueError(f"{dataset} is missing required columns: {sorted(missing)}")
    return frame


def normalize_text(value: object) -> object:
    """Trim whitespace and map explicit null tokens to pandas missing values."""
    if pd.isna(value):
        return pd.NA
    text = re.sub(r"\s+", " ", str(value).strip())
    return pd.NA if text.upper() in MISSING_TOKENS else text


def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize text after source-level duplicate detection has completed."""
    return frame.map(normalize_text)


def standardize_prefixed_id(value: object, prefix: str) -> object:
    """Normalize harmless formatting while retaining the entire identifier body.

    This intentionally never truncates identifiers.  A source identifier that
    cannot provide a body becomes missing and is surfaced in quality metrics.
    """
    if pd.isna(value):
        return pd.NA
    compact = re.sub(r"[^A-Za-z0-9]", "", str(value)).upper()
    if compact.startswith(prefix):
        compact = compact[len(prefix):]
    return f"{prefix}{compact}" if compact else pd.NA


def canonical_token(value: object) -> object:
    """Uppercase a category and represent separators consistently."""
    if pd.isna(value):
        return pd.NA
    token = re.sub(r"[^A-Za-z0-9]+", "_", str(value).strip().upper())
    return token.strip("_") or pd.NA


def money_to_number(value: object) -> object:
    """Parse INR formatted values without coercing malformed values to zero."""
    if pd.isna(value):
        return pd.NA
    text = re.sub(r"(?i)(INR|RS\.?)", "", str(value))
    text = re.sub(r"[^0-9.\-]", "", text.replace(",", ""))
    return pd.to_numeric(text, errors="coerce")


def parse_with_formats(value: object, formats: Iterable[str], *, unix_seconds: bool = True) -> object:
    """Parse only declared timestamp formats and optionally 10-digit Unix seconds."""
    if pd.isna(value):
        return pd.NaT
    text = str(value).strip()
    if not text:
        return pd.NaT
    if unix_seconds and re.fullmatch(r"\d{10}", text):
        return pd.to_datetime(int(text), unit="s", errors="coerce")
    for fmt in formats:
        parsed = pd.to_datetime(text, format=fmt, errors="coerce")
        if not pd.isna(parsed):
            return parsed
    return pd.NaT


def parse_chargeback_timestamp(value: object) -> object:
    """Use the documented chargeback convention: slash=DD/MM, hyphen=MM-DD."""
    return parse_with_formats(
        value,
        (
            "%Y/%m/%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %I:%M %p",
            "%d/%m/%Y", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %I:%M %p",
            "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %I:%M %p",
            "%m-%d-%Y", "%m-%d-%Y %H:%M:%S", "%m-%d-%Y %I:%M %p",
            "%d-%b-%Y", "%d-%b-%Y %H:%M:%S", "%d-%b-%Y %I:%M %p",
        ),
    )


def parse_transaction_timestamp(value: object) -> object:
    """Use the existing transaction cleaning convention for mixed timestamps."""
    return parse_with_formats(
        value,
        (
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y/%m/%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%m-%d-%Y %I:%M:%S %p",
            "%m-%d-%Y %I:%M %p", "%m-%d-%Y", "%d-%m-%Y %I:%M:%S %p",
        ),
    )


def parse_unambiguous_date(value: object) -> object:
    """Parse safe KYC/merchant dates; leave ambiguous numeric dates missing.

    The source mixes DD/MM and MM/DD strings.  Inferring either order where
    both components are <=12 would manufacture a date, so it is flagged rather
    than guessed.
    """
    if pd.isna(value):
        return pd.NaT
    text = str(value).strip()
    if not text:
        return pd.NaT
    if re.fullmatch(r"\d{10}", text):
        return pd.to_datetime(int(text), unit="s", errors="coerce")
    if re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{4}(?: .*)?", text):
        first, second, _ = re.split(r"[/-]", text, maxsplit=2)
        if int(first) <= 12 and int(second) <= 12:
            return pd.NaT
        day_first = int(first) > 12
        formats = (
            "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %I:%M %p", "%d/%m/%Y",
        ) if day_first else (
            "%m-%d-%Y %H:%M:%S", "%m-%d-%Y %I:%M:%S %p", "%m-%d-%Y %I:%M %p", "%m-%d-%Y",
        )
        return parse_with_formats(text, formats, unix_seconds=False)
    return parse_with_formats(
        text,
        (
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d",
            "%d-%b-%Y", "%d-%b-%Y %H:%M:%S", "%d-%b-%Y %I:%M %p",
        ),
        unix_seconds=False,
    )


def coverage(numerator: int | float, denominator: int | float) -> dict[str, float | int]:
    """Return audit-ready numerator, denominator, and percentage."""
    pct = (100 * numerator / denominator) if denominator else 0.0
    return {"numerator": int(numerator), "denominator": int(denominator), "percentage": round(pct, 2)}


def write_csv(frame: pd.DataFrame, filename: str) -> Path:
    """Write a generated CSV under data/processed."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PROCESSED_DIR / filename
    frame.to_csv(path, index=False)
    return path


def write_report(frame: pd.DataFrame, filename: str) -> Path:
    """Write a generated CSV under data/reports."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / filename
    frame.to_csv(path, index=False)
    return path
