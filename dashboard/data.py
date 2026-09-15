"""Cached, dashboard-safe loaders for generated FiniX analytical tables."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "data" / "reports"


@st.cache_data(ttl="15m", max_entries=4, show_spinner="Loading FiniX analytical outputs...")
def load_bundle() -> dict[str, pd.DataFrame]:
    """Load generated analytical outputs once per dashboard session cache."""
    required = {
        "transactions": PROCESSED / "transaction_intelligence.csv",
        "linkage": PROCESSED / "chargeback_linkage.csv",
        "users": PROCESSED / "user_risk_summary.csv",
        "merchants": PROCESSED / "merchant_risk_summary.csv",
        "kyc": PROCESSED / "kyc_user_summary.csv",
        "nodes": PROCESSED / "network_nodes.csv",
        "edges": PROCESSED / "network_edges.csv",
        "validation": REPORTS / "validation_summary.csv",
        "integration_audit": REPORTS / "integration_audit.csv",
        "network_audit": REPORTS / "network_audit.csv",
    }
    missing = [str(path.relative_to(ROOT)) for path in required.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Generated outputs are missing. Run `python -m src.finix.pipeline` first. Missing: " + ", ".join(missing))
    bundle = {name: pd.read_csv(path, low_memory=False) for name, path in required.items()}

    for column in ("timestamp", "matched_transaction_timestamp"):
        if column in bundle["transactions"]:
            bundle["transactions"][column] = pd.to_datetime(bundle["transactions"][column], errors="coerce")
    for column in ("transaction_timestamp", "reported_timestamp", "bank_response_timestamp"):
        if column in bundle["linkage"]:
            bundle["linkage"][column] = pd.to_datetime(bundle["linkage"][column], errors="coerce")
    return bundle


def human_number(value: float | int | None) -> str:
    """Format large counts without hiding the value scale."""
    if value is None or pd.isna(value):
        return "—"
    value = float(value)
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,.0f}"


def inr(value: float | int | None) -> str:
    """Format a monetary value as Indian rupees."""
    if value is None or pd.isna(value):
        return "—"
    return f"₹{float(value):,.2f}"


def safe_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Select only requested columns that are available in a generated table."""
    return frame[[column for column in columns if column in frame.columns]].copy()


def true_mask(series: pd.Series) -> pd.Series:
    """Safely interpret boolean columns after their CSV round trip."""
    return series.astype("string").str.strip().str.lower().isin({"true", "1", "yes"})
