import pandas as pd

import src.finix.network as network


def test_network_calculates_components_and_focal_graph(monkeypatch):
    monkeypatch.setattr(network, "write_csv", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(network, "write_report", lambda *_args, **_kwargs: None)
    transactions = pd.DataFrame({"txn_id": ["TXN1", "TXN2"], "user_id": ["USR1", "USR2"], "merchant_id": ["MCH1", "MCH1"], "amount": [10.0, 20.0]})
    linkage = pd.DataFrame({"complaint_id": ["CBK1"], "user_id": ["USR9"], "merchant_id": ["MCH8"], "disputed_amount": [5.0], "identity_mismatch": [True], "network_disconnected": [True]})
    users = pd.DataFrame({"user_id": ["USR1", "USR2"], "risk_signal_count": [1, 0], "investigation_priority": ["WATCH", "LOW"]})
    merchants = pd.DataFrame({"merchant_id": ["MCH1"], "risk_signal_count": [1], "investigation_priority": ["WATCH"]})
    result = network.build_network(transactions, linkage, users, merchants)
    assert len(result["nodes"]) == 5
    assert result["edges"]["relationship_type"].eq("CHARGEBACK_ONLY").sum() == 1
    nodes, edges = network.focal_network(result["edges"], "USR1")
    assert "USR1" in nodes["node_id"].tolist()
    assert not edges.empty
