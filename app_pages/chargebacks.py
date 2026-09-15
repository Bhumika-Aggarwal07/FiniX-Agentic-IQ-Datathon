import streamlit as st

from dashboard.charts import ranked_bar, time_line
from dashboard.data import human_number, inr, load_bundle, safe_columns, true_mask
from dashboard.ui import page_header


page_header("Chargeback intelligence", "Monitor dispute activity while making record linkage and source-identity differences visible.")
bundle = load_bundle()
linkage = bundle["linkage"].copy()

with st.sidebar:
    st.markdown("### Chargeback filters")
    severities = sorted(linkage["severity"].dropna().unique().tolist())
    selected_severities = st.multiselect("Severity", severities, default=severities)
    statuses = sorted(linkage["linkage_status"].dropna().unique().tolist())
    selected_linkage = st.multiselect("Linkage status", statuses, default=statuses)
    only_mismatch = st.toggle("Only identity mismatches")

filtered = linkage.loc[linkage["severity"].isin(selected_severities) & linkage["linkage_status"].isin(selected_linkage)].copy()
if only_mismatch:
    filtered = filtered.loc[true_mask(filtered["identity_mismatch"])]

metrics = [("Chargebacks", human_number(len(filtered))), ("Disputed amount", inr(filtered["disputed_amount"].sum())), ("High severity", human_number(true_mask(filtered["is_high_severity"]).sum())), ("Identity mismatch", human_number(true_mask(filtered["identity_mismatch"]).sum()))]
for column, (label, value) in zip(st.columns(4), metrics, strict=True):
    column.metric(label, value, border=True)

left, right = st.columns(2)
with left:
    with st.container(border=True):
        reason = filtered.groupby("reason_code", as_index=False).agg(chargeback_count=("complaint_id", "size"))
        st.altair_chart(ranked_bar(reason, "reason_code", "chargeback_count", title="Reason-code distribution", limit=10))
with right:
    with st.container(border=True):
        daily = filtered.dropna(subset=["reported_timestamp"]).assign(date=lambda frame: frame["reported_timestamp"].dt.floor("D")).groupby("date", as_index=False).agg(chargeback_count=("complaint_id", "size"))
        st.altair_chart(time_line(daily, "date", "chargeback_count", title="Reported chargebacks over time"))

st.header("Linkage evidence")
st.info("A mismatch is a record-linkage and investigation signal. FiniX does not overwrite chargeback identities with transaction identities and does not label entities fraudulent.", icon=":material/info:")
columns = ["complaint_id", "txn_id", "user_id", "merchant_id", "transaction_user_id", "transaction_merchant_id", "disputed_amount", "transaction_amount", "reason_code", "severity", "linkage_status", "user_id_match", "merchant_id_match", "network_disconnected", "disputed_amount_match"]
st.dataframe(safe_columns(filtered.sort_values("reported_timestamp", ascending=False).head(300), columns), hide_index=True, column_config={"disputed_amount": st.column_config.NumberColumn("Disputed amount", format="₹%.2f"), "transaction_amount": st.column_config.NumberColumn("Transaction amount", format="₹%.2f")})
