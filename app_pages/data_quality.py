import streamlit as st

from dashboard.data import human_number, load_bundle
from dashboard.ui import page_header


page_header("Data quality", "Evidence for cleaning, validation, and join assurance. Findings remain visible; no raw record is silently corrected or removed beyond exact duplicates.")
bundle = load_bundle()
validation = bundle["validation"]
integration = bundle["integration_audit"]
network = bundle["network_audit"]

metrics = [("Validation checks", human_number(len(validation))), ("Passes", human_number(validation["status"].eq("PASS").sum())), ("Warnings retained", human_number(validation["status"].eq("WARN").sum())), ("Failures", human_number(validation["status"].eq("FAIL").sum()))]
for column, (label, value) in zip(st.columns(4), metrics, strict=True):
    column.metric(label, value, border=True)

st.header("Validation results")
st.dataframe(validation, hide_index=True, column_config={"percentage": st.column_config.NumberColumn("Percentage", format="%.2f%%")})

left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader("Integration coverage")
        st.dataframe(integration, hide_index=True, column_config={"percentage": st.column_config.NumberColumn("Percentage", format="%.2f%%")})
with right:
    with st.container(border=True):
        st.subheader("Network calculation evidence")
        st.dataframe(network, hide_index=True, column_config={"percentage": st.column_config.NumberColumn("Percentage", format="%.2f%%")})

st.info("Warnings identify missingness, repeated reference identities, and other data-quality observations. The pipeline blocks only structural failures that would make downstream results untrustworthy.", icon=":material/fact_check:")
