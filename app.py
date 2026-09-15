"""FiniX Streamlit entry point."""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parent
# Prefer the transparent PNG; fall back to the original JPEG
LOGO_PNG = ROOT / "logo" / "logo.png"
LOGO_JPEG = ROOT / "logo" / "logo.jpeg"
LOGO = LOGO_PNG if LOGO_PNG.is_file() else LOGO_JPEG

st.set_page_config(
    page_title="FiniX | Risk intelligence",
    page_icon=str(LOGO) if LOGO.is_file() else ":material/account_tree:",
    layout="wide",
)

# Remove Streamlit's default white background/border from sidebar image block
st.markdown(
    """
    <style>
    /* Sidebar logo — remove the image wrapper background */
    [data-testid="stSidebar"] img {
        border-radius: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
        padding: 0 !important;
        margin-bottom: 4px;
    }
    /* Remove any stImage container styling */
    [data-testid="stSidebar"] [data-testid="stImage"] > div {
        background: transparent !important;
        border: none !important;
    }
    /* Page header logo */
    [data-testid="stMain"] img {
        border-radius: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
    }
    /* Metric card refinements */
    [data-testid="stMetric"] {
        border-radius: 8px;
    }
    /* Clean sidebar caption spacing */
    [data-testid="stSidebar"] .stCaption {
        margin-top: 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.session_state.setdefault("investigation_query", "")

summary_path = ROOT / "data" / "reports" / "pipeline_run_summary.json"
with st.sidebar:
    if LOGO.is_file():
        st.image(str(LOGO), width=90)
    st.markdown("## FiniX")
    st.caption("UPI fraud-ring and synthetic-identity investigation intelligence")
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        st.caption(f"Generated {summary['generated_at_utc'][:19]} UTC")
    else:
        st.warning("Run the pipeline before opening analysis pages.", icon=":material/play_circle:")
    st.caption("Signals identify investigation candidates. They do not establish fraud.")

page = st.navigation(
    {
        "Executive intelligence": [
            st.Page("app_pages/overview.py", title="Executive overview", icon=":material/dashboard:"),
            st.Page("app_pages/investigation.py", title="Investigation explorer", icon=":material/manage_search:"),
        ],
        "Risk domains": [
            st.Page("app_pages/transactions.py", title="Transaction intelligence", icon=":material/payments:"),
            st.Page("app_pages/chargebacks.py", title="Chargeback intelligence", icon=":material/receipt_long:"),
            st.Page("app_pages/kyc.py", title="KYC and identity", icon=":material/badge:"),
            st.Page("app_pages/merchants.py", title="Merchant risk", icon=":material/storefront:"),
            st.Page("app_pages/network.py", title="Risk network", icon=":material/account_tree:"),
        ],
        "Assurance": [
            st.Page("app_pages/data_quality.py", title="Data quality", icon=":material/fact_check:"),
        ],
    },
    position="sidebar",
)
page.run()
