"""Validation checks with explicit numerators and denominators."""
from __future__ import annotations

from typing import Mapping

import pandas as pd

from .cleaning import CleanResult
from .core import REQUIRED_COLUMNS, write_report


def _row(dataset: str, check: str, numerator: int, denominator: int, status: str, details: str) -> dict[str, object]:
    return {
        "dataset": dataset,
        "check": check,
        "numerator": int(numerator),
        "denominator": int(denominator),
        "percentage": round(100 * numerator / denominator, 2) if denominator else 0.0,
        "status": status,
        "details": details,
    }


def validate_cleaned(results: Mapping[str, CleanResult]) -> pd.DataFrame:
    """Validate schemas, missingness, duplicate rules, and critical keys.

    Warnings report data-quality findings.  They are intentionally not hidden or
    coerced into failures unless a structural prerequisite is violated.
    """
    checks: list[dict[str, object]] = []
    for dataset, result in results.items():
        frame = result.frame
        expected = REQUIRED_COLUMNS[dataset]
        missing_columns = expected - set(frame.columns)
        checks.append(_row(dataset, "required schema columns", len(missing_columns), len(expected), "PASS" if not missing_columns else "FAIL", "Missing: " + ", ".join(sorted(missing_columns)) if missing_columns else "All required source columns are present."))
        checks.append(_row(dataset, "remaining exact duplicate rows", int(frame.duplicated().sum()), len(frame), "PASS" if not frame.duplicated().any() else "WARN", "Only exact source-row duplicates should have been removed."))
        for column, count in frame.isna().sum().items():
            checks.append(_row(dataset, f"missing values: {column}", int(count), len(frame), "WARN" if count else "PASS", "Missing values are preserved rather than imputed."))

    transactions = results["transactions"].frame
    chargebacks = results["chargebacks"].frame
    kyc = results["kyc"].frame
    merchants = results["merchants"].frame
    checks.extend(
        [
            _row("transactions", "unique nonmissing txn_id", int(transactions.loc[transactions["txn_id"].notna(), "txn_id"].duplicated().sum()), int(transactions["txn_id"].notna().sum()), "PASS" if not transactions.loc[transactions["txn_id"].notna(), "txn_id"].duplicated().any() else "FAIL", "Required for chargeback-to-transaction linkage."),
            _row("chargebacks", "unique complaint_id", int(chargebacks.loc[chargebacks["complaint_id"].notna(), "complaint_id"].duplicated().sum()), int(chargebacks["complaint_id"].notna().sum()), "PASS" if not chargebacks.loc[chargebacks["complaint_id"].notna(), "complaint_id"].duplicated().any() else "FAIL", "Each complaint should remain an individually auditable record."),
            _row("kyc", "repeated user_id", int(kyc.loc[kyc["user_id"].notna(), "user_id"].duplicated().sum()), int(kyc["user_id"].notna().sum()), "WARN" if kyc.loc[kyc["user_id"].notna(), "user_id"].duplicated().any() else "PASS", "Repeated KYC profiles are retained and summarized before joining."),
            _row("merchants", "repeated merchant_id", int(merchants.loc[merchants["merchant_id"].notna(), "merchant_id"].duplicated().sum()), int(merchants["merchant_id"].notna().sum()), "WARN" if merchants.loc[merchants["merchant_id"].notna(), "merchant_id"].duplicated().any() else "PASS", "Repeated merchant references are retained and summarized before joining."),
        ]
    )
    for dataset, frame, amount_col in (
        ("transactions", transactions, "amount"),
        ("chargebacks", chargebacks, "disputed_amount"),
        ("kyc", kyc, "monthly_income"),
        ("merchants", merchants, "declared_avg_ticket_size"),
    ):
        checks.append(_row(dataset, f"negative {amount_col} after cleaning", int((frame[amount_col] < 0).sum()), len(frame), "PASS" if not (frame[amount_col] < 0).any() else "FAIL", "Invalid negative monetary values must not remain in the derived numeric field."))
    report = pd.DataFrame(checks)
    write_report(report, "validation_summary.csv")
    return report
