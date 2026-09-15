"""Consistent Altair chart constructors for the FiniX dashboard."""
from __future__ import annotations

import altair as alt
import pandas as pd


def ranked_bar(frame: pd.DataFrame, category: str, value: str, *, title: str, limit: int = 12, currency: bool = False) -> alt.Chart:
    data = frame[[category, value]].dropna().sort_values(value, ascending=False).head(limit).copy()
    tooltip = [alt.Tooltip(f"{category}:N", title=category.replace("_", " ").title()), alt.Tooltip(f"{value}:Q", title=value.replace("_", " ").title(), format=",.2f" if currency else ",.0f")]
    return alt.Chart(data).mark_bar(cornerRadiusEnd=4).encode(
        x=alt.X(f"{value}:Q", title=None),
        y=alt.Y(f"{category}:N", sort="-x", title=None),
        tooltip=tooltip,
    ).properties(title=title, height=max(220, 24 * len(data)))


def time_line(frame: pd.DataFrame, date: str, value: str, *, title: str, currency: bool = False) -> alt.Chart:
    data = frame[[date, value]].dropna().copy()
    return alt.Chart(data).mark_line(point=True).encode(
        x=alt.X(f"{date}:T", title=None),
        y=alt.Y(f"{value}:Q", title=None),
        tooltip=[alt.Tooltip(f"{date}:T", title="Date"), alt.Tooltip(f"{value}:Q", title=value.replace("_", " ").title(), format=",.2f" if currency else ",.0f")],
    ).properties(title=title, height=300)


def network_chart(nodes: pd.DataFrame, edges: pd.DataFrame) -> alt.Chart:
    """Render a bounded, meaningful focal network rather than the whole graph."""
    lines = alt.Chart(edges).mark_rule(opacity=0.6).encode(
        x=alt.X("x:Q", axis=None), y=alt.Y("y:Q", axis=None), x2="x2:Q", y2="y2:Q",
        color=alt.condition("datum.edge_risk_signal", alt.value("#F87171"), alt.value("#64748B")),
        tooltip=[alt.Tooltip("source:N"), alt.Tooltip("target:N"), alt.Tooltip("transaction_count:Q", format=",.0f"), alt.Tooltip("chargeback_count:Q", format=",.0f")],
    )
    points = alt.Chart(nodes).mark_point(filled=True, opacity=0.95).encode(
        x=alt.X("x:Q", axis=None), y=alt.Y("y:Q", axis=None),
        size=alt.Size("degree:Q", scale=alt.Scale(range=[80, 700]), title="Connections"),
        color=alt.Color("node_type:N", title="Entity type"),
        shape=alt.condition("datum.is_focus", alt.value("diamond"), alt.value("circle")),
        tooltip=[alt.Tooltip("node_id:N", title="Entity"), alt.Tooltip("node_type:N", title="Type"), alt.Tooltip("degree:Q", title="Connections")],
    )
    return (lines + points).properties(height=520).configure_view(stroke=None)
