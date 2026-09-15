"""Transaction relationship network metrics and focal-network visual data."""
from __future__ import annotations

from collections.abc import Mapping

import networkx as nx
import pandas as pd

from .core import write_csv, write_report


def build_network(
    transactions: pd.DataFrame,
    linkage: pd.DataFrame,
    users: pd.DataFrame,
    merchants: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Build a bipartite transaction network plus separate chargeback signals.

    Components are calculated only from observed transaction relationships.
    Chargeback-only pairs are included as signal edges but do not retroactively
    make an unobserved relationship a successful transaction connection.
    """
    tx_edges = transactions.groupby(["user_id", "merchant_id"], dropna=False).agg(
        transaction_count=("txn_id", "size"),
        transaction_amount=("amount", "sum"),
    ).reset_index()
    cb_edges = linkage.groupby(["user_id", "merchant_id"], dropna=False).agg(
        chargeback_count=("complaint_id", "size"),
        chargeback_amount=("disputed_amount", "sum"),
        identity_mismatch_count=("identity_mismatch", lambda values: int(values.fillna(False).sum())),
        disconnected_relationship_count=("network_disconnected", lambda values: int(values.fillna(False).sum())),
    ).reset_index()
    edges = tx_edges.merge(cb_edges, on=["user_id", "merchant_id"], how="outer", validate="one_to_one")
    for column in ("transaction_count", "transaction_amount", "chargeback_count", "chargeback_amount", "identity_mismatch_count", "disconnected_relationship_count"):
        edges[column] = pd.to_numeric(edges[column], errors="coerce").fillna(0)
    edges["relationship_type"] = edges["transaction_count"].gt(0).map({True: "TRANSACTION_RELATIONSHIP", False: "CHARGEBACK_ONLY"})
    edges["edge_risk_signal"] = edges["identity_mismatch_count"].gt(0) | edges["disconnected_relationship_count"].gt(0)
    edges = edges.rename(columns={"user_id": "source", "merchant_id": "target"})

    graph = nx.Graph()
    transaction_edges = edges.loc[edges["relationship_type"].eq("TRANSACTION_RELATIONSHIP")]
    for row in transaction_edges.itertuples(index=False):
        graph.add_edge(row.source, row.target, transaction_count=int(row.transaction_count), transaction_amount=float(row.transaction_amount))
    for node in pd.concat([edges["source"], edges["target"]], ignore_index=True).dropna().unique():
        graph.add_node(node)

    component_map: dict[str, tuple[int, int]] = {}
    for component_index, members in enumerate(nx.connected_components(graph), start=1):
        for member in members:
            component_map[str(member)] = (component_index, len(members))

    node_ids = list(graph.nodes())
    nodes = pd.DataFrame({"node_id": node_ids})
    nodes["node_type"] = nodes["node_id"].str.extract(r"^(USR|MCH)", expand=False).map({"USR": "USER", "MCH": "MERCHANT"}).fillna("UNKNOWN")
    nodes["degree"] = nodes["node_id"].map(dict(graph.degree())).fillna(0).astype(int)
    nodes["component_id"] = nodes["node_id"].map(lambda node: component_map.get(str(node), (0, 1))[0]).astype(int)
    nodes["component_size"] = nodes["node_id"].map(lambda node: component_map.get(str(node), (0, 1))[1]).astype(int)
    nodes["transaction_connected_component"] = nodes["component_size"].gt(1)

    user_risk = users[["user_id", "risk_signal_count", "investigation_priority"]].rename(columns={"user_id": "node_id", "risk_signal_count": "risk_signal_count_user", "investigation_priority": "investigation_priority_user"})
    merchant_risk = merchants[["merchant_id", "risk_signal_count", "investigation_priority"]].rename(columns={"merchant_id": "node_id", "risk_signal_count": "risk_signal_count_merchant", "investigation_priority": "investigation_priority_merchant"})
    nodes = nodes.merge(user_risk, on="node_id", how="left").merge(merchant_risk, on="node_id", how="left")
    nodes["risk_signal_count"] = nodes["risk_signal_count_user"].fillna(nodes["risk_signal_count_merchant"]).fillna(0).astype(int)
    nodes["investigation_priority"] = nodes["investigation_priority_user"].fillna(nodes["investigation_priority_merchant"]).fillna("LOW")
    nodes = nodes.drop(columns=["risk_signal_count_user", "risk_signal_count_merchant", "investigation_priority_user", "investigation_priority_merchant"])

    audit = pd.DataFrame(
        [
            {"check": "transaction network nodes", "numerator": len(nodes), "denominator": len(nodes), "percentage": 100.0, "detail": "Users and merchants connected by observed transaction pairs."},
            {"check": "transaction network edges", "numerator": len(transaction_edges), "denominator": len(edges), "percentage": round(100 * len(transaction_edges) / len(edges), 2) if len(edges) else 0.0, "detail": "Observed transaction pairs; chargeback-only pairs remain separate signal edges."},
            {"check": "chargeback-only relationship edges", "numerator": int(edges["relationship_type"].eq("CHARGEBACK_ONLY").sum()), "denominator": len(edges), "percentage": round(100 * edges["relationship_type"].eq("CHARGEBACK_ONLY").mean(), 2) if len(edges) else 0.0, "detail": "Chargeback user-merchant pairs not observed in transaction pairs."},
            {"check": "transaction components", "numerator": len(list(nx.connected_components(graph))), "denominator": len(nodes), "percentage": round(100 * len(list(nx.connected_components(graph))) / len(nodes), 2) if len(nodes) else 0.0, "detail": "Connected components from transactions only."},
        ]
    )
    write_csv(edges, "network_edges.csv")
    write_csv(nodes, "network_nodes.csv")
    write_report(audit, "network_audit.csv")
    return {"nodes": nodes, "edges": edges, "audit": audit}


def focal_network(edges: pd.DataFrame, node_id: str, max_nodes: int = 75) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return a deterministic, bounded two-hop network for an investigation."""
    edge_frame = edges.loc[edges["source"].notna() & edges["target"].notna()].copy()
    graph = nx.Graph()
    for row in edge_frame.itertuples(index=False):
        graph.add_edge(row.source, row.target, edge_risk_signal=bool(row.edge_risk_signal), transaction_count=float(row.transaction_count), chargeback_count=float(row.chargeback_count))
    if node_id not in graph:
        return pd.DataFrame(columns=["node_id", "node_type", "x", "y"]), pd.DataFrame(columns=["source", "target", "x", "y", "x2", "y2", "edge_risk_signal"])
    selected = set(nx.single_source_shortest_path_length(graph, node_id, cutoff=2).keys())
    if len(selected) > max_nodes:
        direct = sorted(graph.neighbors(node_id), key=lambda item: graph.degree(item), reverse=True)
        selected = {node_id, *direct[: max_nodes - 1]}
    subgraph = graph.subgraph(selected).copy()
    positions = nx.spring_layout(subgraph, seed=42, k=1.2 / max(len(subgraph), 1))
    node_frame = pd.DataFrame(
        [
            {"node_id": node, "node_type": "USER" if str(node).startswith("USR") else "MERCHANT", "x": float(position[0]), "y": float(position[1]), "degree": int(subgraph.degree(node)), "is_focus": node == node_id}
            for node, position in positions.items()
        ]
    )
    positions_map: Mapping[str, tuple[float, float]] = {str(node): (float(position[0]), float(position[1])) for node, position in positions.items()}
    selected_edges = edge_frame.loc[edge_frame["source"].isin(selected) & edge_frame["target"].isin(selected)].copy()
    selected_edges["x"] = selected_edges["source"].map(lambda value: positions_map[str(value)][0])
    selected_edges["y"] = selected_edges["source"].map(lambda value: positions_map[str(value)][1])
    selected_edges["x2"] = selected_edges["target"].map(lambda value: positions_map[str(value)][0])
    selected_edges["y2"] = selected_edges["target"].map(lambda value: positions_map[str(value)][1])
    return node_frame, selected_edges
