import pandas as pd
import streamlit as st

from dashboard.charts import ranked_bar, time_line
from dashboard.data import human_number, inr, load_bundle, safe_columns, true_mask
from dashboard.ui import page_header


page_header("Executive overview", "A defensible first view of scale, linkage quality, and investigation candidates. All signals are evidence for review, not fraud conclusions.")
bundle = load_bundle()
transactions = bundle["transactions"]
linkage = bundle["linkage"]
users = bundle["users"]
merchants = bundle["merchants"]
kyc = bundle["kyc"]

identity_mismatch = true_mask(linkage["identity_mismatch"]).sum()
disconnected = true_mask(linkage["network_disconnected"]).sum()
elevated_users = users["investigation_priority"].eq("ELEVATED_REVIEW").sum()
elevated_merchants = merchants["investigation_priority"].eq("ELEVATED_REVIEW").sum()

for labels in (
    [("Transactions", human_number(len(transactions))), ("Transaction value", inr(transactions["amount"].sum())), ("Chargebacks", human_number(len(linkage))), ("Disputed amount", inr(linkage["disputed_amount"].sum()))],
    [("User review candidates", human_number(elevated_users)), ("Merchant review candidates", human_number(elevated_merchants)), ("Identity mismatches", human_number(identity_mismatch)), ("Disconnected relationships", human_number(disconnected))],
):
    columns = st.columns(4)
    for column, (label, value) in zip(columns, labels, strict=True):
        column.metric(label, value, border=True)

st.header("What needs attention")
left, right = st.columns(2)
with left:
    with st.container(border=True):
        daily = transactions.dropna(subset=["timestamp"]).assign(date=lambda frame: frame["timestamp"].dt.floor("D")).groupby("date", as_index=False).agg(transaction_count=("txn_id", "size"), transaction_value=("amount", "sum"))
        st.altair_chart(time_line(daily, "date", "transaction_count", title="Transaction volume over time"))
with right:
    with st.container(border=True):
        priority = merchants[merchants["investigation_priority"].ne("LOW")]
        st.altair_chart(ranked_bar(priority, "merchant_id", "chargeback_count", title="Merchants with chargeback activity", limit=10))

st.header("Investigation queue")
left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader("User candidates")
        user_queue = users.sort_values(["risk_signal_count", "chargeback_count"], ascending=False)
        st.dataframe(safe_columns(user_queue.head(15), ["user_id", "investigation_priority", "risk_signal_count", "transaction_count", "chargeback_count", "identity_mismatch_count", "risk_explanations"]), hide_index=True)
with right:
    with st.container(border=True):
        st.subheader("Merchant candidates")
        merchant_queue = merchants.sort_values(["risk_signal_count", "chargeback_count"], ascending=False)
        st.dataframe(safe_columns(merchant_queue.head(15), ["merchant_id", "merchant_name", "investigation_priority", "risk_signal_count", "transaction_count", "chargeback_count", "chargeback_rate_eligible", "risk_explanations"]), hide_index=True)

st.caption(f"KYC summary covers {human_number(len(kyc))} users. Chargeback linkage retains {human_number(len(linkage))} complaint records without multiplying transaction rows.")
