import pandas as pd

from src.finix.investigation import investigate


def test_investigation_returns_safe_identity_mismatch_response():
    linkage = pd.DataFrame({"complaint_id": ["CBK1"], "txn_id": ["TXN1"], "user_id": ["USR1"], "merchant_id": ["MCH1"], "linkage_status": ["IDENTITY_MISMATCH"], "identity_mismatch": [True], "network_disconnected": [True]})
    data = {"linkage": linkage, "transactions": pd.DataFrame(), "users": pd.DataFrame(), "merchants": pd.DataFrame()}
    result = investigate("Why does this chargeback not match its transaction identity?", data)
    assert result.title == "Chargeback identity mismatches"
    assert "not proof of fraud" in result.explanation
    assert len(result.data) == 1
