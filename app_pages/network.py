import streamlit as st

from dashboard.charts import network_chart, ranked_bar
from dashboard.data import human_number, load_bundle, safe_columns
from dashboard.ui import page_header
from src.finix.network import focal_network


page_header("Risk network", "Graph intelligence is calculated from observed transaction user-merchant relationships; chargeback-only pairs are retained as distinct relationship signals.")
bundle = load_bundle()
nodes = bundle["nodes"]
edges = bundle["edges"]
audit = bundle["network_audit"]

metrics = [("Network nodes", human_number(len(nodes))), ("Relationship edges", human_number(len(edges))), ("Chargeback-only pairs", human_number(edges["relationship_type"].eq("CHARGEBACK_ONLY").sum())), ("Signal edges", human_number(edges["edge_risk_signal"].astype("string").str.lower().eq("true").sum()))]
for column, (label, value) in zip(st.columns(4), metrics, strict=True):
    column.metric(label, value, border=True)

focus_options = sorted(nodes.loc[nodes["degree"].gt(0), "node_id"].tolist())
default_index = 0
if "USR35882" in focus_options:
    default_index = focus_options.index("USR35882")
focus = st.selectbox("Focus entity", focus_options, index=default_index, help="Shows a bounded two-hop neighbourhood so the graph remains interpretable.")
focal_nodes, focal_edges = focal_network(edges, focus)
if focal_nodes.empty:
    st.warning("The selected entity has no graph relationships to display.", icon=":material/warning:")
else:
    with st.container(border=True):
        st.altair_chart(network_chart(focal_nodes, focal_edges))
    st.caption("Grey edges are observed transaction relationships. Red edges carry an identity-mismatch or disconnected-relationship signal. A diamond marks the selected focal entity.")

left, right = st.columns(2)
with left:
    with st.container(border=True):
        high_degree = nodes.sort_values(["degree", "risk_signal_count"], ascending=False)
        st.altair_chart(ranked_bar(high_degree, "node_id", "degree", title="Most connected entities", limit=12))
with right:
    with st.container(border=True):
        st.subheader("Computed network checks")
        st.dataframe(audit, hide_index=True)

st.header("Focal relationship evidence")
st.dataframe(safe_columns(focal_edges.sort_values(["edge_risk_signal", "chargeback_count", "transaction_count"], ascending=False), ["source", "target", "relationship_type", "transaction_count", "transaction_amount", "chargeback_count", "chargeback_amount", "identity_mismatch_count", "disconnected_relationship_count", "edge_risk_signal"]), hide_index=True)
