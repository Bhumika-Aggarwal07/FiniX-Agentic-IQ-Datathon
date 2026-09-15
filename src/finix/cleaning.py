"""Dataset-specific cleaning routines for FiniX.

Only exact source-row duplicates are removed.  Cross-dataset identities are
never altered here; those discrepancies are handled by the integration layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from .core import (
    canonical_token,
    money_to_number,
    normalize_frame,
    parse_chargeback_timestamp,
    parse_transaction_timestamp,
    parse_unambiguous_date,
    read_raw,
    standardize_prefixed_id,
    write_csv,
    write_report,
)


@dataclass
class CleanResult:
    """A cleaned dataset accompanied by auditable cleaning metrics."""

    dataset: str
    frame: pd.DataFrame
    audit: pd.DataFrame


def _audit_row(issue: str, column: str, rule: str, affected: int, denominator: int) -> dict[str, object]:
    return {
        "dataset": issue.split(" ")[0].lower(),
        "issue": issue,
        "column": column,
        "rule": rule,
        "numerator": int(affected),
        "denominator": int(denominator),
        "percentage": round(100 * affected / denominator, 2) if denominator else 0.0,
    }


def _source_deduplicate(dataset: str) -> tuple[pd.DataFrame, list[dict[str, object]], int]:
    raw = read_raw(dataset)
    raw_rows = len(raw)
    duplicate_mask = raw.duplicated(keep="first")
    deduplicated = raw.loc[~duplicate_mask].copy()
    audit = [
        _audit_row(
            f"{dataset} exact duplicates removed",
            "ALL",
            "Remove exact rows only in their raw source representation.",
            int(duplicate_mask.sum()),
            raw_rows,
        )
    ]
    return normalize_frame(deduplicated).reset_index(drop=True), audit, raw_rows


def _id_clean(frame: pd.DataFrame, column: str, prefix: str, audit: list[dict[str, object]], raw_rows: int, dataset: str) -> None:
    before = frame[column].copy()
    frame[column] = frame[column].map(lambda value: standardize_prefixed_id(value, prefix)).astype("string")
    changed = int((before.astype("string") != frame[column]).fillna(False).sum())
    missing = int(frame[column].isna().sum())
    audit.append(_audit_row(f"{dataset} ID standardization", column, f"Canonical {prefix} identifier; no truncation.", changed, raw_rows))
    audit.append(_audit_row(f"{dataset} missing identifier", column, "Preserve absent or malformed identifier as missing.", missing, len(frame)))


def _parse_money(frame: pd.DataFrame, column: str, audit: list[dict[str, object]], raw_rows: int, dataset: str) -> None:
    source = frame[column].copy()
    numeric = source.map(money_to_number)
    invalid_negative = numeric.lt(0).fillna(False)
    parse_failure = source.notna() & numeric.isna()
    frame[f"{column}_invalid_flag"] = invalid_negative.astype(bool)
    frame[f"{column}_parse_failure_flag"] = parse_failure.astype(bool)
    frame[column] = numeric.mask(invalid_negative).astype("Float64")
    audit.append(_audit_row(f"{dataset} invalid negative monetary values", column, "Flag and preserve as missing; do not reverse sign.", int(invalid_negative.sum()), raw_rows))
    audit.append(_audit_row(f"{dataset} monetary parse failures", column, "Malformed present values become missing and are flagged.", int(parse_failure.sum()), raw_rows))


def _parse_datetime_column(
    frame: pd.DataFrame,
    column: str,
    parser: Callable[[object], object],
    audit: list[dict[str, object]],
    raw_rows: int,
    dataset: str,
) -> None:
    source = frame[column].copy()
    parsed = source.map(parser)
    parse_failure = source.notna() & parsed.isna()
    frame[f"{column}_parse_failure_flag"] = parse_failure.astype(bool)
    frame[column] = pd.to_datetime(parsed, errors="coerce")
    audit.append(_audit_row(f"{dataset} timestamp parse failures", column, "Unsupported or ambiguous timestamps become missing and are flagged.", int(parse_failure.sum()), raw_rows))


def _canonicalize(frame: pd.DataFrame, column: str, mapping: dict[str, str], audit: list[dict[str, object]], raw_rows: int, dataset: str) -> None:
    token = frame[column].map(canonical_token)
    unmapped = token.notna() & ~token.isin(mapping)
    frame[f"{column}_unmapped_flag"] = unmapped.astype(bool)
    frame[column] = token.map(mapping).fillna(token).astype("string")
    audit.append(_audit_row(f"{dataset} unmapped category values", column, "Retain normalized unexpected categories and flag them.", int(unmapped.sum()), raw_rows))


def clean_transactions() -> CleanResult:
    """Clean UPI transaction records without joining other datasets."""
    df, audit, raw_rows = _source_deduplicate("transactions")
    for column, prefix in (("txn_id", "TXN"), ("user_id", "USR"), ("merchant_id", "MCH"), ("utr", "UTR")):
        _id_clean(df, column, prefix, audit, raw_rows, "transactions")

    _parse_money(df, "amount", audit, raw_rows, "transactions")
    _parse_datetime_column(df, "timestamp", parse_transaction_timestamp, audit, raw_rows, "transactions")

    raw_mcc = df["mcc"].copy()
    df["mcc"] = raw_mcc.map(lambda value: pd.NA if pd.isna(value) else str(value).replace("MCC", "").replace("-", "").replace(" ", "").replace(".0", ""))
    df["mcc_valid"] = df["mcc"].astype("string").str.fullmatch(r"\d{4}", na=False)
    audit.append(_audit_row("transactions invalid MCC", "mcc", "Accept exactly four digits after removing presentation prefixes.", int((df["mcc"].notna() & ~df["mcc_valid"]).sum()), raw_rows))

    _canonicalize(
        df,
        "status",
        {
            "S": "COMPLETED", "SUCCESS": "COMPLETED", "TXN_SUCCESS": "COMPLETED", "COMPLETED": "COMPLETED",
            "F": "FAILED", "FAILED": "FAILED", "FAIL": "FAILED", "TXN_FAILED": "FAILED", "DECLINED": "FAILED",
            "PENDING": "PENDING", "P": "PENDING", "PROCESSING": "PENDING", "INITIATED": "PENDING",
        },
        audit,
        raw_rows,
        "transactions",
    )
    for column, count in df.isna().sum().items():
        audit.append(_audit_row("transactions missing values after cleaning", column, "Preserve missingness; no imputation.", int(count), len(df)))
    return CleanResult("transactions", df, pd.DataFrame(audit))


def clean_kyc() -> CleanResult:
    """Clean KYC records independently; sensitive fields remain out of dashboard tables."""
    df, audit, raw_rows = _source_deduplicate("kyc")
    _id_clean(df, "user_id", "USR", audit, raw_rows, "kyc")

    df["pan"] = df["pan"].map(lambda value: pd.NA if pd.isna(value) else str(value).replace(" ", "").replace("-", "").upper()).astype("string")
    df["pan_valid"] = df["pan"].str.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", na=False)
    audit.append(_audit_row("kyc invalid PAN", "pan", "Uppercase and validate the PAN shape; never correct a value.", int((df["pan"].notna() & ~df["pan_valid"]).sum()), raw_rows))

    df["aadhaar"] = df["aadhaar"].map(lambda value: pd.NA if pd.isna(value) else "".join(character for character in str(value) if character.isdigit())).astype("string")
    df["aadhaar_valid"] = df["aadhaar"].str.fullmatch(r"\d{12}", na=False)
    audit.append(_audit_row("kyc invalid Aadhaar", "aadhaar", "Retain digits and validate twelve-digit shape; never create a value.", int((df["aadhaar"].notna() & ~df["aadhaar_valid"]).sum()), raw_rows))

    _parse_money(df, "monthly_income", audit, raw_rows, "kyc")
    _parse_datetime_column(df, "date_of_birth", parse_unambiguous_date, audit, raw_rows, "kyc")
    _parse_datetime_column(df, "signup_timestamp", parse_unambiguous_date, audit, raw_rows, "kyc")
    for column in ("city", "state", "occupation"):
        df[column] = df[column].map(canonical_token).astype("string")
    _canonicalize(
        df,
        "kyc_status",
        {
            "VERIFIED": "VERIFIED", "V": "VERIFIED", "APPROVED": "VERIFIED", "DONE": "VERIFIED", "KYC_DONE": "VERIFIED",
            "PENDING": "PENDING", "P": "PENDING", "IN_PROGRESS": "PENDING", "UNDER_REVIEW": "PENDING",
            "REJECTED": "REJECTED", "R": "REJECTED", "REJECT": "REJECTED", "FAILED": "REJECTED",
        },
        audit,
        raw_rows,
        "kyc",
    )
    _canonicalize(
        df,
        "risk_segment",
        {"LOW": "LOW", "MEDIUM": "MEDIUM", "HIGH": "HIGH", "UNKNOWN": "UNKNOWN"},
        audit,
        raw_rows,
        "kyc",
    )
    for column, count in df.isna().sum().items():
        audit.append(_audit_row("kyc missing values after cleaning", column, "Preserve missingness; no imputation.", int(count), len(df)))
    return CleanResult("kyc", df, pd.DataFrame(audit))


def clean_merchants() -> CleanResult:
    """Clean merchant master records independently from transaction performance."""
    df, audit, raw_rows = _source_deduplicate("merchants")
    _id_clean(df, "merchant_id", "MCH", audit, raw_rows, "merchants")
    raw_mcc = df["mcc"].copy()
    df["mcc"] = raw_mcc.map(lambda value: pd.NA if pd.isna(value) else str(value).upper().replace("MCC", "").replace("-", "").replace(" ", "").replace(".0", "")).astype("string")
    df["mcc_valid"] = df["mcc"].str.fullmatch(r"\d{4}", na=False)
    audit.append(_audit_row("merchants invalid MCC", "mcc", "Accept exactly four digits after removing presentation prefixes.", int((df["mcc"].notna() & ~df["mcc_valid"]).sum()), raw_rows))
    df["settlement_account"] = df["settlement_account"].map(lambda value: pd.NA if pd.isna(value) else "".join(character for character in str(value).upper() if character.isalnum())).astype("string")
    df["settlement_account_valid"] = df["settlement_account"].str.fullmatch(r"[A-Z0-9]{9,18}", na=False)
    audit.append(_audit_row("merchants invalid settlement account", "settlement_account", "Validate alphanumeric account shape; preserve invalid source values.", int((df["settlement_account"].notna() & ~df["settlement_account_valid"]).sum()), raw_rows))
    _parse_money(df, "declared_avg_ticket_size", audit, raw_rows, "merchants")
    _parse_datetime_column(df, "onboarding_date", parse_unambiguous_date, audit, raw_rows, "merchants")
    for column in ("merchant_category", "business_type", "city", "state"):
        df[column] = df[column].map(canonical_token).astype("string")
    _canonicalize(
        df,
        "merchant_status",
        {
            "ACTIVE": "ACTIVE", "A": "ACTIVE", "ENABLED": "ACTIVE", "LIVE": "ACTIVE",
            "INACTIVE": "INACTIVE", "I": "INACTIVE", "DISABLED": "INACTIVE", "CLOSED": "INACTIVE",
            "SUSPENDED": "SUSPENDED", "S": "SUSPENDED", "BLOCKED": "SUSPENDED", "HOLD": "SUSPENDED",
        },
        audit,
        raw_rows,
        "merchants",
    )
    for column, count in df.isna().sum().items():
        audit.append(_audit_row("merchants missing values after cleaning", column, "Preserve missingness; no imputation.", int(count), len(df)))
    return CleanResult("merchants", df, pd.DataFrame(audit))


def clean_chargebacks() -> CleanResult:
    """Clean chargebacks and retain source identity mismatches for integration."""
    df, audit, raw_rows = _source_deduplicate("chargebacks")
    for column, prefix in (("complaint_id", "CBK"), ("txn_id", "TXN"), ("user_id", "USR"), ("merchant_id", "MCH")):
        _id_clean(df, column, prefix, audit, raw_rows, "chargebacks")
    _parse_money(df, "disputed_amount", audit, raw_rows, "chargebacks")
    for column in ("transaction_timestamp", "reported_timestamp", "bank_response_timestamp"):
        _parse_datetime_column(df, column, parse_chargeback_timestamp, audit, raw_rows, "chargebacks")

    df["reported_before_transaction_flag"] = (
        df["reported_timestamp"].notna() & df["transaction_timestamp"].notna() & (df["reported_timestamp"] < df["transaction_timestamp"])
    )
    df["bank_response_before_transaction_flag"] = (
        df["bank_response_timestamp"].notna() & df["transaction_timestamp"].notna() & (df["bank_response_timestamp"] < df["transaction_timestamp"])
    )
    for column, flag in (("reported_timestamp", "reported_before_transaction_flag"), ("bank_response_timestamp", "bank_response_before_transaction_flag")):
        affected = int(df[flag].sum())
        df.loc[df[flag], column] = pd.NaT
        audit.append(_audit_row("chargebacks impossible chronology", column, "Flag timestamp before transaction and set the derived value to missing.", affected, raw_rows))

    _canonicalize(
        df,
        "reason_code",
        {
            "CHARGED_TWICE": "DUPLICATE_DEBIT", "DUP_DEBIT": "DUPLICATE_DEBIT", "DUPLICATE_DEBIT": "DUPLICATE_DEBIT", "DOUBLE_DEBIT": "DUPLICATE_DEBIT",
            "AMOUNT_MISMATCH": "AMOUNT_MISMATCH", "WRONG_AMOUNT": "AMOUNT_MISMATCH", "EXTRA_AMOUNT_DEDUCTED": "AMOUNT_MISMATCH", "INCORRECT_AMOUNT": "AMOUNT_MISMATCH",
            "ATO": "ACCOUNT_TAKEOVER", "ACCOUNT_TAKEOVER": "ACCOUNT_TAKEOVER", "ACCOUNT_HACKED": "ACCOUNT_TAKEOVER", "LOGIN_COMPROMISED": "ACCOUNT_TAKEOVER",
            "MERCHANT_NOT_DELIVERED": "SERVICE_NOT_PROVIDED", "SERVICE_NOT_PROVIDED": "SERVICE_NOT_PROVIDED", "DELIVERY_ISSUE": "SERVICE_NOT_PROVIDED", "ITEM_NOT_RECEIVED": "SERVICE_NOT_PROVIDED", "MERCHANT_SERVICE_ISSUE": "SERVICE_NOT_PROVIDED", "NO_SERVICE": "SERVICE_NOT_PROVIDED", "NOT_DELIVERED": "SERVICE_NOT_PROVIDED", "SERVICE_FAILED": "SERVICE_NOT_PROVIDED",
            "CUSTOMER_DISPUTE": "CUSTOMER_DISPUTE", "CUSTOMER_ISSUE": "CUSTOMER_DISPUTE", "DISPUTE_RAISED": "CUSTOMER_DISPUTE", "COMPLAINT": "CUSTOMER_DISPUTE",
            "FRAUD": "UNAUTHORIZED_TRANSACTION", "FRAUD_SUSPECTED": "UNAUTHORIZED_TRANSACTION", "NOT_DONE_BY_ME": "UNAUTHORIZED_TRANSACTION", "SCAM": "UNAUTHORIZED_TRANSACTION", "SUSPICIOUS_TRANSACTION": "UNAUTHORIZED_TRANSACTION", "UNAUTH_TXN": "UNAUTHORIZED_TRANSACTION", "UNAUTHORISED": "UNAUTHORIZED_TRANSACTION", "UNAUTHORIZED_TRANSACTION": "UNAUTHORIZED_TRANSACTION",
        },
        audit,
        raw_rows,
        "chargebacks",
    )
    _canonicalize(df, "resolution_status", {"CLOSED": "CLOSED", "IN_PROGRESS": "IN_PROGRESS", "WIP": "IN_PROGRESS", "OPEN": "OPEN", "PENDING_BANK": "PENDING_BANK", "REJECTED": "REJECTED", "RESOLVED": "RESOLVED"}, audit, raw_rows, "chargebacks")
    _canonicalize(df, "severity", {"CRIT": "CRITICAL", "CRITICAL": "CRITICAL", "P1": "CRITICAL", "H": "HIGH", "HIGH": "HIGH", "P2": "HIGH", "M": "MEDIUM", "MEDIUM": "MEDIUM", "P3": "MEDIUM", "L": "LOW", "LOW": "LOW", "P4": "LOW"}, audit, raw_rows, "chargebacks")
    _canonicalize(df, "channel", {"APP": "APP", "BRANCH": "BRANCH", "CHATBOT": "CHATBOT", "CALL_CENTER": "CALL_CENTER", "EMAIL": "EMAIL", "IVR": "IVR"}, audit, raw_rows, "chargebacks")
    df["complaint_text"] = df["complaint_text"].astype("string").str.strip()
    for column, count in df.isna().sum().items():
        audit.append(_audit_row("chargebacks missing values after cleaning", column, "Preserve missingness; no imputation.", int(count), len(df)))
    return CleanResult("chargebacks", df, pd.DataFrame(audit))


def clean_all() -> dict[str, CleanResult]:
    """Execute each independent cleaner and persist its data and audit report."""
    results = {
        "transactions": clean_transactions(),
        "kyc": clean_kyc(),
        "merchants": clean_merchants(),
        "chargebacks": clean_chargebacks(),
    }
    output_names = {
        "transactions": "transactions_cleaned.csv",
        "kyc": "kyc_cleaned.csv",
        "merchants": "merchants_cleaned.csv",
        "chargebacks": "chargebacks_cleaned.csv",
    }
    for dataset, result in results.items():
        write_csv(result.frame, output_names[dataset])
        write_report(result.audit, f"{dataset}_cleaning_audit.csv")
    return results
