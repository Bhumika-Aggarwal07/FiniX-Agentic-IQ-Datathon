import streamlit as st

from dashboard.charts import ranked_bar
from dashboard.data import human_number, load_bundle, safe_columns, true_mask
from dashboard.ui import page_header


page_header("KYC and identity risk", "Profile-level KYC coverage and consistency indicators. PAN, Aadhaar, full names, and other sensitive values are not exposed in this dashboard.")
bundle = load_bundle()
kyc = bundle["kyc"].copy()

metrics = [("KYC users", human_number(len(kyc))), ("Rejected KYC records", human_number(kyc["rejected_kyc_records"].sum())), ("High-risk KYC records", human_number(kyc["high_risk_kyc_records"].sum())), ("Inconsistent profiles", human_number(true_mask(kyc["profile_inconsistency_flag"]).sum()))]
for column, (label, value) in zip(st.columns(4), metrics, strict=True):
    column.metric(label, value, border=True)

left, right = st.columns(2)
with left:
    with st.container(border=True):
        status = kyc.groupby("latest_kyc_status", dropna=False, as_index=False).agg(user_count=("user_id", "size"))
        st.altair_chart(ranked_bar(status, "latest_kyc_status", "user_count", title="Latest KYC status", limit=10))
with right:
    with st.container(border=True):
        risk = kyc.groupby("latest_risk_segment", dropna=False, as_index=False).agg(user_count=("user_id", "size"))
        st.altair_chart(ranked_bar(risk, "latest_risk_segment", "user_count", title="Latest KYC risk segment", limit=10))

st.header("KYC linkage and consistency")
display = kyc.sort_values(["rejected_kyc_records", "high_risk_kyc_records", "profile_inconsistency_flag"], ascending=False)
columns = ["user_id", "latest_kyc_status", "latest_risk_segment", "kyc_record_count", "kyc_status_values", "risk_segment_values", "rejected_kyc_records", "high_risk_kyc_records", "pending_kyc_records", "profile_inconsistency_flag", "invalid_pan_records", "invalid_aadhaar_records"]
st.dataframe(safe_columns(display.head(300), columns), hide_index=True)
