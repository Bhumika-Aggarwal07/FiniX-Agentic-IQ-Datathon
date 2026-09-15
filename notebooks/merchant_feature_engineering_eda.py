"""Independent merchant feature engineering, EDA, charts, and findings report.

Input:  data/processed/merchants_cleaned.csv
Outputs: data/processed/merchants_featured.csv, reports/merchant_key_findings.md,
         reports/figures/merchant_*.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

INPUT = Path("data/processed/merchants_cleaned.csv")
OUTPUT = Path("data/processed/merchants_featured.csv")
REPORT = Path("reports/merchant_key_findings.md")
FIGURES = Path("reports/figures")
ANALYSIS_DATE = pd.Timestamp("2026-09-14")
sns.set_theme(style="whitegrid", palette="deep")


def is_missing(series: pd.Series) -> pd.Series:
    return series.isna() | series.astype("string").str.strip().eq("")


def quantile_band(series: pd.Series) -> pd.Series:
    result = pd.Series(pd.NA, index=series.index, dtype="string")
    values = series.dropna()
    if not values.empty:
        result.loc[values.index] = pd.qcut(values.rank(method="first"), 4,
                                             labels=["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]).astype("string")
    return result


def iqr_limits(series: pd.Series) -> tuple[float, float, pd.Series]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    q1, q3 = values.quantile([.25, .75])
    lower, upper = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    numeric = pd.to_numeric(series, errors="coerce")
    return float(lower), float(upper), (numeric < lower) | (numeric > upper)


def md_table(df: pd.DataFrame, limit: int = 12) -> str:
    df = df.head(limit).fillna("NULL")
    lines = ["| " + " | ".join(map(str, df.columns)) + " |", "| " + " | ".join(["---"] * len(df.columns)) + " |"]
    lines += ["| " + " | ".join(str(x).replace("|", "\\|") for x in row) + " |" for row in df.astype(str).itertuples(index=False, name=None)]
    return "\n".join(lines) if not df.empty else "_No records._"


def feature_engineer(df: pd.DataFrame) -> pd.DataFrame:
    """Add merchant features only; KYC data is never read or joined."""
    required = {"mcc", "merchant_category", "business_type", "settlement_account", "merchant_status", "declared_avg_ticket_size", "onboarding_date"}
    absent = sorted(required - set(df.columns))
    if absent:
        raise ValueError(f"Merchant input is missing columns: {', '.join(absent)}")
    df = df.copy()
    df["declared_avg_ticket_size"] = pd.to_numeric(df["declared_avg_ticket_size"], errors="coerce")
    df["missing_mcc"] = is_missing(df["mcc"])
    df["missing_category"] = is_missing(df["merchant_category"])
    df["missing_business_type"] = is_missing(df["business_type"])
    df["missing_settlement_account"] = is_missing(df["settlement_account"])
    df["ticket_size_band"] = quantile_band(df["declared_avg_ticket_size"])
    df["onboarding_date"] = pd.to_datetime(df["onboarding_date"], errors="coerce", format="mixed")
    df["merchant_age_days"] = (ANALYSIS_DATE - df["onboarding_date"]).dt.days.astype("Int64")
    df["merchant_age_months"] = (df["merchant_age_days"] / 30.4375).round().astype("Int64")
    df["onboarding_year"] = df["onboarding_date"].dt.year.astype("Int64")
    df["onboarding_month"] = df["onboarding_date"].dt.month.astype("Int64")
    df["onboarding_quarter"] = df["onboarding_date"].dt.quarter.astype("Int64")
    status = df["merchant_status"].astype("string").str.upper()
    df["is_active"] = status.isin(["ACTIVE", "A"])
    df["is_inactive"] = status.isin(["INACTIVE", "I"])
    df["is_suspended"] = status.isin(["SUSPENDED", "S"])
    high_ticket = df["declared_avg_ticket_size"].quantile(.75)
    df["active_missing_mcc"] = df["is_active"] & df["missing_mcc"]
    df["active_missing_category"] = df["is_active"] & df["missing_category"]
    df["inactive_high_ticket_size"] = df["is_inactive"] & df["declared_avg_ticket_size"].ge(high_ticket)
    df["suspended_high_ticket_size"] = df["is_suspended"] & df["declared_avg_ticket_size"].ge(high_ticket)
    return df


def create_charts(df: pd.DataFrame) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    for column, title, filename in [("merchant_category", "Merchant category distribution", "merchant_category_distribution.png"), ("merchant_status", "Merchant-status distribution", "merchant_status_distribution.png"), ("city", "Top merchant cities", "merchant_city_distribution.png")]:
        fig, ax = plt.subplots(figsize=(9, 5))
        df[column].fillna("MISSING").value_counts().head(12).sort_values().plot.barh(ax=ax, color="#3478bf")
        ax.set(title=title, xlabel="Merchants", ylabel="")
        fig.tight_layout(); fig.savefig(FIGURES / filename, dpi=160); plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, 5))
    sns.boxplot(data=df.dropna(subset=["declared_avg_ticket_size"]), x="merchant_category", y="declared_avg_ticket_size", ax=ax)
    ax.tick_params(axis="x", rotation=35); ax.set_title("Ticket size by merchant category")
    fig.tight_layout(); fig.savefig(FIGURES / "merchant_ticket_by_category.png", dpi=160); plt.close(fig)


def write_findings(df: pd.DataFrame) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    lower, upper, outliers = iqr_limits(df["declared_avg_ticket_size"])
    missing = df[["missing_mcc", "missing_category", "missing_business_type", "missing_settlement_account"]].sum().rename_axis("field").reset_index(name="merchants")
    categories = df["merchant_category"].value_counts(dropna=False).rename_axis("merchant_category").reset_index(name="merchants")
    mcc = df["mcc"].value_counts(dropna=False).rename_axis("mcc").reset_index(name="merchants")
    business = df["business_type"].value_counts(dropna=False).rename_axis("business_type").reset_index(name="merchants")
    status = df["merchant_status"].value_counts(dropna=False).rename_axis("merchant_status").reset_index(name="merchants")
    ticket = df["declared_avg_ticket_size"].describe(percentiles=[.25, .5, .75]).rename_axis("metric").reset_index(name="ticket_size")
    category_ticket = df.groupby("merchant_category")["declared_avg_ticket_size"].agg(["count", "mean", "median"]).sort_values("median", ascending=False).reset_index()
    high = df.nlargest(10, "declared_avg_ticket_size")[["merchant_id", "merchant_name", "merchant_category", "declared_avg_ticket_size"]]
    low = df.dropna(subset=["declared_avg_ticket_size"]).nsmallest(10, "declared_avg_ticket_size")[["merchant_id", "merchant_name", "merchant_category", "declared_avg_ticket_size"]]
    geography = df["city"].value_counts().rename_axis("city").reset_index(name="merchants")
    suspicious = df[["active_missing_mcc", "active_missing_category", "inactive_high_ticket_size", "suspended_high_ticket_size"]].sum().rename_axis("flag").reset_index(name="merchants")
    REPORT.write_text(f"""# Merchant Master Key Findings

## Scope
This report analyzes **{len(df):,}** merchant records only. KYC, transaction, and chargeback data was not read, joined, or merged.

## Data quality
{md_table(missing)}

## Categories, MCCs, business types, and statuses
{md_table(categories)}

{md_table(mcc)}

{md_table(business)}

{md_table(status)}

## Ticket-size analysis
{md_table(ticket)}

The IQR bounds are **{lower:,.2f}** to **{upper:,.2f}**; **{int(outliers.sum()):,}** ticket sizes are outliers. These deserve review, not automatic exclusion.

{md_table(category_ticket)}

Highest ticket-size merchants:

{md_table(high)}

Lowest ticket-size merchants:

{md_table(low)}

## Geography and suspicious-profile flags
{md_table(geography)}

{md_table(suspicious)}

Flags indicate operational-review candidates and are not fraud determinations.
""", encoding="utf-8")


def main() -> None:
    if not INPUT.exists():
        raise FileNotFoundError(f"Cleaned merchant file not found: {INPUT.resolve()}")
    df = feature_engineer(pd.read_csv(INPUT, low_memory=False))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False)
    create_charts(df)
    write_findings(df)
    print(f"Created {OUTPUT} with {len(df):,} merchant records.")


if __name__ == "__main__":
    main()
