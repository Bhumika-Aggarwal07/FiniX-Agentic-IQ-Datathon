"""Feature engineering, guarded integration, and explainable risk marts."""
from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd

from .cleaning import CleanResult
from .core import write_csv, write_report


MIN_MERCHANT_TRANSACTION_VOLUME = 5


def _bool_sum(series: pd.Series) -> int:
    return int(series.fillna(False).astype(bool).sum())


def _q(series: pd.Series, quantile: float) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return float(values.quantile(quantile)) if not values.empty else 0.0


def _stable_values(series: pd.Series) -> str:
    values = sorted({str(value) for value in series.dropna() if str(value)})
    return " | ".join(values)


def _representative(series: pd.Series) -> object:
    values = sorted({str(value) for value in series.dropna() if str(value)})
    if not values:
        return pd.NA
    return values[0] if len(values) == 1 else "MULTIPLE_VALUES"


def engineer_features(cleaned: Mapping[str, CleanResult]) -> dict[str, pd.DataFrame]:
    """Derive analytical features only from each dataset's own cleaned data."""
    transactions = cleaned["transactions"].frame.copy()
    transactions["transaction_date"] = transactions["timestamp"].dt.date
    transactions["transaction_hour"] = transactions["timestamp"].dt.hour.astype("Int64")
    transactions["transaction_day_of_week"] = transactions["timestamp"].dt.day_name().astype("string")
    transactions["is_completed_transaction"] = transactions["status"].eq("COMPLETED")
    transactions["is_failed_transaction"] = transactions["status"].eq("FAILED")
    transactions["is_pending_transaction"] = transactions["status"].eq("PENDING")
    amount_threshold = _q(transactions["amount"], 0.95)
    transactions["is_high_value_transaction"] = transactions["amount"].ge(amount_threshold)
    transactions["user_transaction_count"] = transactions.groupby("user_id", dropna=False)["txn_id"].transform("size").astype("Int64")
    transactions["merchant_transaction_count"] = transactions.groupby("merchant_id", dropna=False)["txn_id"].transform("size").astype("Int64")
    transactions["user_amount_zscore"] = _group_zscore(transactions, "user_id", "amount")
    transactions["is_user_amount_anomaly"] = transactions["user_amount_zscore"].abs().ge(2.5).fillna(False)

    chargebacks = cleaned["chargebacks"].frame.copy()
    chargebacks["reporting_delay_hours"] = (chargebacks["reported_timestamp"] - chargebacks["transaction_timestamp"]).dt.total_seconds() / 3600
    chargebacks["bank_response_delay_hours"] = (chargebacks["bank_response_timestamp"] - chargebacks["reported_timestamp"]).dt.total_seconds() / 3600
    chargebacks["bank_response_before_report_flag"] = chargebacks["bank_response_delay_hours"].lt(0).fillna(False)
    chargebacks["is_critical_dispute"] = chargebacks["severity"].eq("CRITICAL")
    chargebacks["is_high_severity"] = chargebacks["severity"].isin(["CRITICAL", "HIGH"])
    chargebacks["is_open_case"] = chargebacks["resolution_status"].isin(["OPEN", "IN_PROGRESS", "PENDING_BANK"])
    chargebacks["is_account_takeover"] = chargebacks["reason_code"].eq("ACCOUNT_TAKEOVER")
    chargebacks["is_unauthorized_transaction"] = chargebacks["reason_code"].eq("UNAUTHORIZED_TRANSACTION")
    dispute_threshold = _q(chargebacks["disputed_amount"], 0.75)
    chargebacks["is_high_value_dispute"] = chargebacks["disputed_amount"].ge(dispute_threshold)
    chargebacks["chargeback_date"] = chargebacks["reported_timestamp"].dt.date

    kyc = cleaned["kyc"].frame.copy()
    reference_date = pd.Timestamp("2026-09-15")
    kyc["age_years"] = np.floor((reference_date - kyc["date_of_birth"]).dt.days / 365.2425).astype("Int64")
    kyc["age_invalid_flag"] = kyc["age_years"].lt(18).fillna(False) | kyc["age_years"].gt(120).fillna(False)
    kyc["is_kyc_rejected"] = kyc["kyc_status"].eq("REJECTED")
    kyc["is_kyc_pending"] = kyc["kyc_status"].eq("PENDING")
    kyc["is_high_kyc_risk"] = kyc["risk_segment"].eq("HIGH")
    kyc["is_high_income_profile"] = kyc["monthly_income"].ge(_q(kyc["monthly_income"], 0.95))

    merchants = cleaned["merchants"].frame.copy()
    merchants["merchant_age_days"] = (reference_date - merchants["onboarding_date"]).dt.days.astype("Int64")
    merchants["future_onboarding_flag"] = merchants["merchant_age_days"].lt(0).fillna(False)
    merchants["is_active_merchant"] = merchants["merchant_status"].eq("ACTIVE")
    merchants["is_suspended_merchant"] = merchants["merchant_status"].eq("SUSPENDED")
    merchants["is_high_declared_ticket"] = merchants["declared_avg_ticket_size"].ge(_q(merchants["declared_avg_ticket_size"], 0.95))
    merchants["active_missing_mcc"] = merchants["is_active_merchant"] & merchants["mcc"].isna()

    outputs = {
        "transactions": transactions,
        "chargebacks": chargebacks,
        "kyc": kyc,
        "merchants": merchants,
    }
    for dataset, frame in outputs.items():
        filename = "chargeback_features.csv" if dataset == "chargebacks" else f"{dataset}_features.csv"
        write_csv(frame, filename)
    return outputs


def _group_zscore(frame: pd.DataFrame, group: str, numeric: str) -> pd.Series:
    values = pd.to_numeric(frame[numeric], errors="coerce")
    grouped_mean = values.groupby(frame[group], dropna=False).transform("mean")
    grouped_std = values.groupby(frame[group], dropna=False).transform("std")
    return ((values - grouped_mean) / grouped_std.replace(0, np.nan)).astype("Float64")


def build_kyc_summary(kyc: pd.DataFrame) -> pd.DataFrame:
    """Create one safe, explicit KYC summary row per user without exposing PII."""
    ordered = kyc.assign(_order=np.arange(len(kyc))).sort_values(["user_id", "signup_timestamp", "_order"], na_position="first")
    latest = ordered.groupby("user_id", dropna=False).tail(1).set_index("user_id")
    grouped = kyc.groupby("user_id", dropna=False)
    summary = grouped.agg(
        kyc_record_count=("user_id", "size"),
        kyc_status_values=("kyc_status", _stable_values),
        kyc_status_count=("kyc_status", "nunique"),
        risk_segment_values=("risk_segment", _stable_values),
        risk_segment_count=("risk_segment", "nunique"),
        rejected_kyc_records=("is_kyc_rejected", _bool_sum),
        high_risk_kyc_records=("is_high_kyc_risk", _bool_sum),
        pending_kyc_records=("is_kyc_pending", _bool_sum),
        median_monthly_income=("monthly_income", "median"),
        city_values=("city", _stable_values),
        occupation_values=("occupation", _stable_values),
        invalid_pan_records=("pan_valid", lambda values: int((~values.fillna(False)).sum())),
        invalid_aadhaar_records=("aadhaar_valid", lambda values: int((~values.fillna(False)).sum())),
    ).reset_index()
    summary = summary.merge(latest[["kyc_status", "risk_segment", "signup_timestamp"]].rename(columns={"kyc_status": "latest_kyc_status", "risk_segment": "latest_risk_segment", "signup_timestamp": "latest_signup_timestamp"}), on="user_id", how="left", validate="one_to_one")
    summary["profile_inconsistency_flag"] = summary["kyc_status_count"].gt(1) | summary["risk_segment_count"].gt(1)
    write_csv(summary, "kyc_user_summary.csv")
    return summary


def build_merchant_reference_summary(merchants: pd.DataFrame) -> pd.DataFrame:
    """Resolve repeated master records into a single, transparent merchant summary."""
    grouped = merchants.groupby("merchant_id", dropna=False)
    summary = grouped.agg(
        merchant_reference_record_count=("merchant_id", "size"),
        merchant_name=("merchant_name", _representative),
        merchant_category=("merchant_category", _representative),
        business_type=("business_type", _representative),
        merchant_status=("merchant_status", _representative),
        mcc=("mcc", _representative),
        city=("city", _representative),
        state=("state", _representative),
        declared_avg_ticket_size=("declared_avg_ticket_size", "median"),
        merchant_status_values=("merchant_status", _stable_values),
        merchant_category_values=("merchant_category", _stable_values),
        merchant_status_count=("merchant_status", "nunique"),
        merchant_category_count=("merchant_category", "nunique"),
        invalid_mcc_records=("mcc_valid", lambda values: int((~values.fillna(False)).sum())),
        suspended_reference_records=("is_suspended_merchant", _bool_sum),
    ).reset_index()
    summary["merchant_reference_inconsistency_flag"] = summary["merchant_status_count"].gt(1) | summary["merchant_category_count"].gt(1)
    write_csv(summary, "merchant_reference_summary.csv")
    return summary


def _linkage_audit_row(check: str, numerator: int, denominator: int, detail: str) -> dict[str, object]:
    return {
        "check": check,
        "numerator": int(numerator),
        "denominator": int(denominator),
        "percentage": round(100 * numerator / denominator, 2) if denominator else 0.0,
        "detail": detail,
    }


def integrate(features: Mapping[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Join validated source summaries while preserving original chargeback IDs.

    Transactions remain one row per transaction. Chargebacks remain one row per
    complaint, avoiding a hidden one-to-many multiplication in either fact.
    """
    transactions = features["transactions"].copy()
    chargebacks = features["chargebacks"].copy()
    kyc_summary = build_kyc_summary(features["kyc"])
    merchant_summary = build_merchant_reference_summary(features["merchants"])

    transaction_enriched = transactions.merge(kyc_summary, on="user_id", how="left", validate="many_to_one")
    transaction_enriched = transaction_enriched.merge(merchant_summary, on="merchant_id", how="left", validate="many_to_one", suffixes=("", "_merchant"))

    transaction_lookup = transactions[["txn_id", "user_id", "merchant_id", "amount", "status", "timestamp"]].rename(
        columns={
            "user_id": "transaction_user_id",
            "merchant_id": "transaction_merchant_id",
            "amount": "transaction_amount",
            "status": "transaction_status",
            "timestamp": "matched_transaction_timestamp",
        }
    )
    if transaction_lookup["txn_id"].duplicated().any():
        raise ValueError("Cannot integrate: cleaned transaction txn_id is not unique.")
    linkage = chargebacks.merge(transaction_lookup, on="txn_id", how="left", validate="many_to_one")
    if len(linkage) != len(chargebacks):
        raise ValueError("Chargeback linkage changed row count; refusing a join explosion.")

    linkage["transaction_record_found"] = linkage["transaction_user_id"].notna()
    linkage["txn_id_match"] = linkage["transaction_record_found"]
    linkage["user_id_match"] = pd.array(np.where(linkage["transaction_record_found"], linkage["user_id"].eq(linkage["transaction_user_id"]), pd.NA), dtype="boolean")
    linkage["merchant_id_match"] = pd.array(np.where(linkage["transaction_record_found"], linkage["merchant_id"].eq(linkage["transaction_merchant_id"]), pd.NA), dtype="boolean")
    linkage["user_merchant_pair_match"] = pd.array(np.where(linkage["transaction_record_found"], linkage["user_id_match"].fillna(False) & linkage["merchant_id_match"].fillna(False), pd.NA), dtype="boolean")

    transaction_pairs = pd.MultiIndex.from_frame(transactions[["user_id", "merchant_id"]])
    chargeback_pairs = pd.MultiIndex.from_frame(linkage[["user_id", "merchant_id"]])
    linkage["network_disconnected"] = ~chargeback_pairs.isin(transaction_pairs)
    amount_available = linkage["disputed_amount"].notna() & linkage["transaction_amount"].notna()
    amount_match = linkage["disputed_amount"].round(2).eq(linkage["transaction_amount"].round(2))
    linkage["disputed_amount_match"] = pd.array(np.where(amount_available, amount_match, pd.NA), dtype="boolean")
    linkage["identity_mismatch"] = linkage["transaction_record_found"] & (~linkage["user_id_match"].fillna(False) | ~linkage["merchant_id_match"].fillna(False))
    linkage["data_quality_anomaly"] = linkage[["disputed_amount_invalid_flag", "reported_before_transaction_flag", "bank_response_before_transaction_flag"]].fillna(False).astype(bool).any(axis=1)
    linkage["linkage_status"] = np.select(
        [
            linkage["txn_id"].isna(),
            ~linkage["transaction_record_found"],
            linkage["identity_mismatch"],
            linkage["network_disconnected"],
        ],
        ["MISSING_TXN_ID", "UNMATCHED_TRANSACTION", "IDENTITY_MISMATCH", "RELATIONSHIP_MISMATCH"],
        default="MATCHED_IDENTITIES",
    )

    cb_by_txn = linkage.groupby("txn_id", dropna=False).agg(
        chargeback_count=("complaint_id", "size"),
        chargeback_amount=("disputed_amount", "sum"),
        high_severity_chargeback_count=("is_high_severity", _bool_sum),
        identity_mismatch_count=("identity_mismatch", _bool_sum),
        disconnected_relationship_count=("network_disconnected", _bool_sum),
    ).reset_index()
    transaction_enriched = transaction_enriched.merge(cb_by_txn, on="txn_id", how="left", validate="one_to_one")
    for column in ("chargeback_count", "chargeback_amount", "high_severity_chargeback_count", "identity_mismatch_count", "disconnected_relationship_count"):
        transaction_enriched[column] = transaction_enriched[column].fillna(0)

    audit = pd.DataFrame(
        [
            _linkage_audit_row("chargeback records retained after linkage", len(linkage), len(chargebacks), "One linkage record remains per chargeback complaint."),
            _linkage_audit_row("transactions found for chargebacks", int(linkage["transaction_record_found"].sum()), len(linkage), "Linked by standardized txn_id without identity replacement."),
            _linkage_audit_row("chargebacks missing txn_id", int(linkage["txn_id"].isna().sum()), len(linkage), "Cannot be linked to a transaction."),
            _linkage_audit_row("chargebacks with identity mismatch", int(linkage["identity_mismatch"].sum()), int(linkage["transaction_record_found"].sum()), "Observed source discrepancy, not a fraud determination."),
            _linkage_audit_row("chargeback pairs disconnected from transaction network", int(linkage["network_disconnected"].sum()), len(linkage), "Chargeback user-merchant pair is not observed in transaction pairs."),
            _linkage_audit_row("exact disputed amount matches", int(linkage["disputed_amount_match"].fillna(False).sum()), int(amount_available.sum()), "Exact two-decimal comparison where both values exist."),
            _linkage_audit_row("transaction rows retained after chargeback aggregation", len(transaction_enriched), len(transactions), "Chargeback aggregates are joined, never raw one-to-many chargeback rows."),
        ]
    )
    write_csv(transaction_enriched, "transaction_intelligence.csv")
    write_csv(linkage, "chargeback_linkage.csv")
    write_report(audit, "integration_audit.csv")
    return {"transactions": transaction_enriched, "chargeback_linkage": linkage, "kyc_summary": kyc_summary, "merchant_summary": merchant_summary, "integration_audit": audit}


def build_risk_marts(integrated: Mapping[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Produce transparent user and merchant investigation summaries."""
    transactions = integrated["transactions"]
    linkage = integrated["chargeback_linkage"]
    kyc = integrated["kyc_summary"]
    merchant_reference = integrated["merchant_summary"]

    user_txn = transactions.groupby("user_id", dropna=False).agg(
        transaction_count=("txn_id", "size"), total_transaction_value=("amount", "sum"), average_transaction_value=("amount", "mean"),
        unique_merchants=("merchant_id", "nunique"), failed_transaction_count=("is_failed_transaction", _bool_sum), pending_transaction_count=("is_pending_transaction", _bool_sum),
        high_value_transaction_count=("is_high_value_transaction", _bool_sum), amount_anomaly_count=("is_user_amount_anomaly", _bool_sum),
    ).reset_index()
    user_cb = linkage.groupby("user_id", dropna=False).agg(
        chargeback_count=("complaint_id", "size"), disputed_amount=("disputed_amount", "sum"), high_severity_chargeback_count=("is_high_severity", _bool_sum),
        unauthorized_transaction_count=("is_unauthorized_transaction", _bool_sum), account_takeover_count=("is_account_takeover", _bool_sum),
        identity_mismatch_count=("identity_mismatch", _bool_sum), disconnected_relationship_count=("network_disconnected", _bool_sum),
    ).reset_index()
    all_users = pd.DataFrame({"user_id": pd.concat([transactions["user_id"], linkage["user_id"], kyc["user_id"]], ignore_index=True).dropna().unique()})
    users = all_users.merge(user_txn, on="user_id", how="left").merge(user_cb, on="user_id", how="left").merge(kyc, on="user_id", how="left", validate="one_to_one")
    _fill_counts(users)
    users["high_transaction_frequency_flag"] = users["transaction_count"].ge(_q(users["transaction_count"], 0.95)) & users["transaction_count"].gt(0)
    users["high_chargeback_activity_flag"] = users["chargeback_count"].ge(_q(users["chargeback_count"], 0.95)) & users["chargeback_count"].gt(0)
    users["risk_signal_count"], users["risk_explanations"] = _risk_explanations(users, "user")
    users["investigation_priority"] = _priority(users["risk_signal_count"])

    merchant_txn = transactions.groupby("merchant_id", dropna=False).agg(
        transaction_count=("txn_id", "size"), total_transaction_value=("amount", "sum"), average_transaction_value=("amount", "mean"),
        unique_users=("user_id", "nunique"), failed_transaction_count=("is_failed_transaction", _bool_sum),
    ).reset_index()
    merchant_cb = linkage.groupby("merchant_id", dropna=False).agg(
        chargeback_count=("complaint_id", "size"), chargeback_amount=("disputed_amount", "sum"), high_severity_chargeback_count=("is_high_severity", _bool_sum),
        identity_mismatch_count=("identity_mismatch", _bool_sum), disconnected_relationship_count=("network_disconnected", _bool_sum),
    ).reset_index()
    all_merchants = pd.DataFrame({"merchant_id": pd.concat([transactions["merchant_id"], linkage["merchant_id"], merchant_reference["merchant_id"]], ignore_index=True).dropna().unique()})
    merchants = all_merchants.merge(merchant_txn, on="merchant_id", how="left").merge(merchant_cb, on="merchant_id", how="left").merge(merchant_reference, on="merchant_id", how="left", validate="one_to_one")
    _fill_counts(merchants)
    merchants["chargeback_records_per_transaction"] = np.where(merchants["transaction_count"].gt(0), merchants["chargeback_count"] / merchants["transaction_count"], np.nan)
    merchants["chargeback_rate_eligible"] = merchants["transaction_count"].ge(MIN_MERCHANT_TRANSACTION_VOLUME)
    merchants["chargeback_rate_min_volume"] = merchants["chargeback_records_per_transaction"].where(merchants["chargeback_rate_eligible"])
    merchants["ticket_size_variance_ratio"] = (merchants["average_transaction_value"] / merchants["declared_avg_ticket_size"]).replace([np.inf, -np.inf], np.nan)
    eligible_rates = merchants.loc[merchants["chargeback_rate_eligible"], "chargeback_rate_min_volume"]
    merchants["high_chargeback_rate_flag"] = merchants["chargeback_rate_min_volume"].ge(_q(eligible_rates, 0.90)).fillna(False) & merchants["chargeback_rate_eligible"]
    merchants["high_chargeback_activity_flag"] = merchants["chargeback_count"].ge(_q(merchants["chargeback_count"], 0.95)) & merchants["chargeback_count"].gt(0)
    merchants["risk_signal_count"], merchants["risk_explanations"] = _risk_explanations(merchants, "merchant")
    merchants["investigation_priority"] = _priority(merchants["risk_signal_count"])

    write_csv(users, "user_risk_summary.csv")
    write_csv(merchants, "merchant_risk_summary.csv")
    return {"users": users, "merchants": merchants}


def _fill_counts(frame: pd.DataFrame) -> None:
    for column in frame.columns:
        if column.endswith("_count") or column in {"transaction_count", "chargeback_count", "disputed_amount", "chargeback_amount", "total_transaction_value", "average_transaction_value", "unique_merchants", "unique_users"}:
            frame[column] = pd.to_numeric(frame[column].astype(object), errors="coerce").fillna(0)


def _priority(signal_count: pd.Series) -> pd.Series:
    return pd.cut(signal_count, bins=[-1, 0, 2, np.inf], labels=["LOW", "WATCH", "ELEVATED_REVIEW"]).astype("string")


def _risk_explanations(frame: pd.DataFrame, entity: str) -> tuple[pd.Series, pd.Series]:
    explanations: list[str] = []
    counts: list[int] = []
    for _, row in frame.iterrows():
        reasons: list[str] = []
        if _is_true(row.get("high_transaction_frequency_flag", False)):
            reasons.append("unusually high transaction frequency")
        if _is_true(row.get("high_chargeback_activity_flag", False)):
            reasons.append("high chargeback activity")
        if _number(row.get("identity_mismatch_count", 0)) > 0:
            reasons.append("chargeback identity mismatch")
        if _number(row.get("disconnected_relationship_count", 0)) > 0:
            reasons.append("disconnected user-merchant relationship")
        if entity == "user":
            if _number(row.get("rejected_kyc_records", 0)) > 0:
                reasons.append("rejected KYC record")
            if _number(row.get("high_risk_kyc_records", 0)) > 0:
                reasons.append("high-risk KYC segment")
            if _number(row.get("unauthorized_transaction_count", 0)) > 0:
                reasons.append("unauthorized-transaction chargeback")
        else:
            if _is_true(row.get("high_chargeback_rate_flag", False)):
                reasons.append(f"high chargeback activity at at least {MIN_MERCHANT_TRANSACTION_VOLUME} transactions")
            if _is_true(row.get("merchant_reference_inconsistency_flag", False)):
                reasons.append("inconsistent merchant-master records")
            if _number(row.get("suspended_reference_records", 0)) > 0:
                reasons.append("suspended merchant-master status")
        counts.append(len(reasons))
        explanations.append("; ".join(reasons) if reasons else "No elevated analytical signals in the available data.")
    return pd.Series(counts, index=frame.index, dtype="Int64"), pd.Series(explanations, index=frame.index, dtype="string")


def _is_true(value: object) -> bool:
    """Interpret nullable booleans safely in live in-memory analytical frames."""
    return bool(value) if pd.notna(value) else False


def _number(value: object) -> float:
    """Convert a nullable numeric value to a safe zero default."""
    return float(value) if pd.notna(value) else 0.0
