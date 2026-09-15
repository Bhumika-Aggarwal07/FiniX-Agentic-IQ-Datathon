import pandas as pd
import streamlit as st

from dashboard.charts import ranked_bar, time_line
from dashboard.data import human_number, inr, load_bundle, safe_columns, true_mask
from dashboard.ui import page_header


page_header("Transaction intelligence", "Explore UPI transaction activity, status patterns, and high-value or unusual activity candidates.")
bundle = load_bundle()
transactions = bundle["transactions"].copy()

with st.sidebar:
    st.markdown("### Transaction filters")
    statuses = sorted(transactions["status"].dropna().unique().tolist())
    selected_statuses = st.multiselect("Transaction status", statuses, default=statuses)
    dates = transactions["timestamp"].dropna()
    if not dates.empty:
        selected_dates = st.date_input("Transaction date range", value=(dates.min().date(), dates.max().date()), min_value=dates.min().date(), max_value=dates.max().date())
    else:
        selected_dates = None
    only_chargebacks = st.toggle("Only transactions with chargebacks")

filtered = transactions.loc[transactions["status"].isin(selected_statuses)].copy()
if selected_dates and len(selected_dates) == 2:
    filtered = filtered.loc[filtered["timestamp"].dt.date.between(selected_dates[0], selected_dates[1])]
if only_chargebacks:
    filtered = filtered.loc[filtered["chargeback_count"].gt(0)]

columns = st.columns(4)
metrics = [("Filtered transactions", human_number(len(filtered))), ("Transaction value", inr(filtered["amount"].sum())), ("Failed", human_number(true_mask(filtered["is_failed_transaction"]).sum())), ("High-value candidates", human_number(true_mask(filtered["is_high_value_transaction"]).sum()))]
for column, (label, value) in zip(columns, metrics, strict=True):
    column.metric(label, value, border=True)

left, right = st.columns(2)
with left:
    with st.container(border=True):
        daily = filtered.dropna(subset=["timestamp"]).assign(date=lambda frame: frame["timestamp"].dt.floor("D")).groupby("date", as_index=False).agg(transaction_count=("txn_id", "size"))
        st.altair_chart(time_line(daily, "date", "transaction_count", title="Transaction count over time"))
with right:
    with st.container(border=True):
        status = filtered.groupby("status", as_index=False).agg(transaction_count=("txn_id", "size"))
        st.altair_chart(ranked_bar(status, "status", "transaction_count", title="Status distribution", limit=10))

st.header("Highest-value and chargeback-linked transactions")
candidate_columns = ["txn_id", "timestamp", "user_id", "merchant_id", "amount", "status", "is_high_value_transaction", "is_user_amount_anomaly", "chargeback_count", "identity_mismatch_count"]
st.dataframe(safe_columns(filtered.sort_values(["chargeback_count", "amount"], ascending=False).head(250), candidate_columns), hide_index=True, column_config={"amount": st.column_config.NumberColumn("Amount", format="₹%.2f")})
