"""Deterministic, data-backed natural-language investigation fallback."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

import pandas as pd


@dataclass
class InvestigationResult:
    """A safe response built solely from generated analytical tables."""

    title: str
    explanation: str
    data: pd.DataFrame
    chart: str = "table"


EXAMPLES = (
    "Why is USR35882 an investigation candidate?",
    "Show merchants with high chargeback activity but low transaction volume.",
    "Find users connected to more than 5 merchants.",
    "Why does this chargeback not match its transaction identity?",
    "Find disconnected user-merchant relationships.",
)


def investigate(query: str, data: Mapping[str, pd.DataFrame]) -> InvestigationResult:
    """Route supported questions to deterministic tables and explanations.

    This is intentionally not an LLM.  It does not infer facts outside the
    generated dataset and does not claim that an entity is fraudulent.
    """
    clean_query = (query or "").strip()
    normalized = clean_query.upper()
    if not clean_query:
        return InvestigationResult("Investigation query", "Enter an entity ID or one of the suggested questions.", pd.DataFrame())
    identifiers = {
        "user": _extract(normalized, r"USR[A-Z0-9]+"),
        "merchant": _extract(normalized, r"MCH[A-Z0-9]+"),
        "transaction": _extract(normalized, r"TXN[A-Z0-9]+"),
        "chargeback": _extract(normalized, r"CBK[A-Z0-9]+"),
    }
    if identifiers["chargeback"]:
        return _chargeback_result(identifiers["chargeback"], data)
    if identifiers["transaction"]:
        return _transaction_result(identifiers["transaction"], data)
    if identifiers["user"]:
        return _user_result(identifiers["user"], data)
    if identifiers["merchant"]:
        return _merchant_result(identifiers["merchant"], data)
    if "DISCONNECTED" in normalized or "RELATIONSHIP MISMATCH" in normalized:
        rows = data["linkage"].loc[data["linkage"]["network_disconnected"].fillna(False), _safe_linkage_columns(data["linkage"])]
        rows = _newest_first(rows)
        return InvestigationResult("Disconnected user-merchant relationships", "These chargeback user-merchant pairs do not occur among the observed transaction pairs. This is an analytical relationship signal, not proof of fraud.", rows, "table")
    if "IDENTITY MISMATCH" in normalized or "NOT MATCH" in normalized or "MISMATCH" in normalized:
        rows = data["linkage"].loc[data["linkage"]["identity_mismatch"].fillna(False), _safe_linkage_columns(data["linkage"])]
        rows = _newest_first(rows)
        return InvestigationResult("Chargeback identity mismatches", "Each row links by txn_id but differs from the linked transaction on the user or merchant identity. Original source values are preserved; this is not proof of fraud.", rows, "table")
    if "MERCHANT" in normalized and ("CHARGEBACK" in normalized or "LOW TRANSACTION" in normalized):
        merchants = data["merchants"].copy()
        rows = merchants.loc[(merchants["chargeback_count"] > 0) & (merchants["transaction_count"] <= merchants["transaction_count"].quantile(0.25)), _safe_merchant_columns(merchants)].sort_values(["chargeback_count", "transaction_count"], ascending=[False, True])
        return InvestigationResult("Merchants with chargeback activity and low transaction volume", "The table retains absolute counts. Rate comparisons are only available once a merchant has the configured minimum transaction volume.", rows, "bar")
    if "USER" in normalized and ("MORE THAN" in normalized or "CONNECTED" in normalized):
        match = re.search(r"MORE\s+THAN\s+(\d+)", normalized)
        threshold = int(match.group(1)) if match else 5
        users = data["users"].copy()
        rows = users.loc[users["unique_merchants"] > threshold, _safe_user_columns(users)].sort_values("unique_merchants", ascending=False)
        return InvestigationResult(f"Users connected to more than {threshold} merchants", "Counterparty counts are calculated from observed transactions; they identify breadth of activity for review.", rows, "bar")
    return InvestigationResult("Supported investigation patterns", "I can investigate a user, merchant, transaction, or chargeback ID, or answer one of the suggested data-backed questions.", pd.DataFrame({"Example queries": EXAMPLES}))


def _extract(query: str, pattern: str) -> str | None:
    match = re.search(pattern, query)
    return match.group(0) if match else None


def _user_result(user_id: str, data: Mapping[str, pd.DataFrame]) -> InvestigationResult:
    users = data["users"]
    profile = users.loc[users["user_id"].eq(user_id), _safe_user_columns(users)]
    if profile.empty:
        return InvestigationResult(f"User {user_id}", "No user record was found in the generated analytical tables.", profile)
    row = profile.iloc[0]
    detail = data["transactions"].loc[data["transactions"]["user_id"].eq(user_id), [column for column in ("txn_id", "timestamp", "merchant_id", "amount", "status", "chargeback_count") if column in data["transactions"].columns]].sort_values("timestamp", ascending=False)
    explanation = f"{user_id} is classified as {row['investigation_priority']} based on observed signals: {row['risk_explanations']} The available data is insufficient to establish fraud."
    return InvestigationResult(f"User investigation: {user_id}", explanation, detail, "table")


def _merchant_result(merchant_id: str, data: Mapping[str, pd.DataFrame]) -> InvestigationResult:
    merchants = data["merchants"]
    profile = merchants.loc[merchants["merchant_id"].eq(merchant_id), _safe_merchant_columns(merchants)]
    if profile.empty:
        return InvestigationResult(f"Merchant {merchant_id}", "No merchant record was found in the generated analytical tables.", profile)
    row = profile.iloc[0]
    detail = data["transactions"].loc[data["transactions"]["merchant_id"].eq(merchant_id), [column for column in ("txn_id", "timestamp", "user_id", "amount", "status", "chargeback_count") if column in data["transactions"].columns]].sort_values("timestamp", ascending=False)
    explanation = f"{merchant_id} is classified as {row['investigation_priority']} based on observed signals: {row['risk_explanations']} Chargeback ratios are accompanied by their transaction denominators and do not establish fraud."
    return InvestigationResult(f"Merchant investigation: {merchant_id}", explanation, detail, "table")


def _transaction_result(txn_id: str, data: Mapping[str, pd.DataFrame]) -> InvestigationResult:
    row = data["transactions"].loc[data["transactions"]["txn_id"].eq(txn_id)]
    if row.empty:
        return InvestigationResult(f"Transaction {txn_id}", "No transaction record was found in the generated analytical tables.", row)
    linkage = data["linkage"].loc[data["linkage"]["txn_id"].eq(txn_id), _safe_linkage_columns(data["linkage"])]
    chargeback_count = int(row.iloc[0].get("chargeback_count", 0))
    explanation = f"Transaction {txn_id} has {chargeback_count} linked chargeback record(s). Linkage details below distinguish a matched transaction from source identity or relationship differences."
    return InvestigationResult(f"Transaction investigation: {txn_id}", explanation, linkage, "table")


def _chargeback_result(complaint_id: str, data: Mapping[str, pd.DataFrame]) -> InvestigationResult:
    row = data["linkage"].loc[data["linkage"]["complaint_id"].eq(complaint_id), _safe_linkage_columns(data["linkage"])]
    if row.empty:
        return InvestigationResult(f"Chargeback {complaint_id}", "No chargeback record was found in the generated analytical tables.", row)
    record = row.iloc[0]
    explanation = f"Chargeback {complaint_id} has linkage status {record['linkage_status']}. This status describes available record linkage and observed differences; it is not a fraud conclusion."
    return InvestigationResult(f"Chargeback investigation: {complaint_id}", explanation, row, "table")


def _safe_user_columns(frame: pd.DataFrame) -> list[str]:
    preferred = ["user_id", "investigation_priority", "risk_signal_count", "risk_explanations", "transaction_count", "total_transaction_value", "average_transaction_value", "unique_merchants", "chargeback_count", "disputed_amount", "high_severity_chargeback_count", "identity_mismatch_count", "disconnected_relationship_count", "latest_kyc_status", "latest_risk_segment"]
    return [column for column in preferred if column in frame.columns]


def _safe_merchant_columns(frame: pd.DataFrame) -> list[str]:
    preferred = ["merchant_id", "merchant_name", "merchant_category", "merchant_status", "investigation_priority", "risk_signal_count", "risk_explanations", "transaction_count", "total_transaction_value", "average_transaction_value", "chargeback_count", "chargeback_amount", "chargeback_records_per_transaction", "chargeback_rate_eligible", "chargeback_rate_min_volume", "identity_mismatch_count", "disconnected_relationship_count", "declared_avg_ticket_size", "ticket_size_variance_ratio"]
    return [column for column in preferred if column in frame.columns]


def _safe_linkage_columns(frame: pd.DataFrame) -> list[str]:
    preferred = ["complaint_id", "txn_id", "user_id", "merchant_id", "transaction_user_id", "transaction_merchant_id", "disputed_amount", "transaction_amount", "reason_code", "severity", "reported_timestamp", "linkage_status", "txn_id_match", "user_id_match", "merchant_id_match", "user_merchant_pair_match", "network_disconnected", "disputed_amount_match", "data_quality_anomaly"]
    return [column for column in preferred if column in frame.columns]


def _newest_first(frame: pd.DataFrame) -> pd.DataFrame:
    """Sort on report time only where the provided table contains it."""
    return frame.sort_values("reported_timestamp", ascending=False) if "reported_timestamp" in frame.columns else frame
