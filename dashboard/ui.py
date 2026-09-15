"""Small native-Streamlit presentation helpers."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

_LOGO_PNG = Path(__file__).resolve().parents[1] / "logo" / "logo.png"
_LOGO_JPEG = Path(__file__).resolve().parents[1] / "logo" / "logo.jpeg"
_LOGO = _LOGO_PNG if _LOGO_PNG.is_file() else _LOGO_JPEG


def page_header(title: str, subtitle: str) -> None:
    """Render a consistent page heading with the FiniX logo and concise analyst-facing context."""
    col_title, col_logo = st.columns([9, 1])
    with col_title:
        st.title(title)
        st.caption(subtitle)
    with col_logo:
        if _LOGO.is_file():
            st.image(str(_LOGO), width=72)


def candidate_badge(priority: object) -> None:
    """Render investigation priority without implying a fraud conclusion."""
    color = {"ELEVATED_REVIEW": "orange", "WATCH": "blue", "LOW": "green"}.get(str(priority), "gray")
    st.badge(str(priority).replace("_", " ").title(), color=color)
