import numpy as np
import streamlit as st

from dashboard.charts import ranked_bar
from dashboard.data import human_number, inr, load_bundle, safe_columns
from dashboard.ui import page_header


page_header("Merchant risk", "Rank merchant activity with raw counts, protected ratios, declared ticket sizes, and documented master-data consistency signals.")
bundle = load_bundle()
merchants = bundle["merchants"].copy()

with st.sidebar:
    st.markdown("### Merchant filters")
    minimum_volume = st.number_input("Minimum transaction volume", min_value=0, max_value=int(merchants["transaction_count"].max()), value=5, step=1, help="Chargeback-rate views require this many transactions. Counts remain visible at every volume.")
    priorities = sorted(merchants["investigation_priority"].dropna().unique().tolist())
    selected_priorities = st.multiselect("Investigation priority", priorities, default=priorities)

filtered = merchants.loc[merchants["transaction_count"].ge(minimum_volume) & merchants["investigation_priority"].isin(selected_priorities)].copy()
eligible = filtered.loc[filtered["chargeback_rate_eligible"].astype("string").str.lower().eq("true")]

metrics = [("Merchants in view", human_number(len(filtered))), ("Transaction volume", human_number(filtered["transaction_count"].sum())), ("Chargeback records", human_number(filtered["chargeback_count"].sum())), ("Rate-eligible merchants", human_number(len(eligible)))]
for column, (label, value) in zip(st.columns(4), metrics, strict=True):
    column.metric(label, value, border=True)

left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.altair_chart(ranked_bar(filtered, "merchant_id", "total_transaction_value", title="Top merchants by transaction value", limit=12, currency=True))
with right:
    with st.container(border=True):
        st.altair_chart(ranked_bar(filtered, "merchant_id", "chargeback_count", title="Top merchants by chargeback count", limit=12))

st.header("Rate context and ticket-size comparison")
st.caption("Chargeback records per transaction are a relationship metric, not a fraud rate. FiniX suppresses the filtered-rate field below the minimum-volume rule while retaining raw counts.")
display = filtered.assign(ticket_size_variance_ratio=lambda frame: frame["ticket_size_variance_ratio"].replace([np.inf, -np.inf], np.nan))
columns = ["merchant_id", "merchant_name", "merchant_category", "merchant_status", "investigation_priority", "transaction_count", "total_transaction_value", "average_transaction_value", "declared_avg_ticket_size", "ticket_size_variance_ratio", "chargeback_count", "chargeback_amount", "chargeback_records_per_transaction", "chargeback_rate_eligible", "chargeback_rate_min_volume", "identity_mismatch_count", "risk_explanations"]
st.dataframe(safe_columns(display.sort_values(["chargeback_count", "transaction_count"], ascending=False).head(300), columns), hide_index=True, column_config={"total_transaction_value": st.column_config.NumberColumn("Transaction value", format="₹%.2f"), "average_transaction_value": st.column_config.NumberColumn("Actual average ticket", format="₹%.2f"), "declared_avg_ticket_size": st.column_config.NumberColumn("Declared average ticket", format="₹%.2f"), "chargeback_amount": st.column_config.NumberColumn("Chargeback amount", format="₹%.2f"), "chargeback_records_per_transaction": st.column_config.NumberColumn("Raw CB records / transaction", format="%.3f"), "chargeback_rate_min_volume": st.column_config.NumberColumn("Min-volume relationship metric", format="%.3f")})
