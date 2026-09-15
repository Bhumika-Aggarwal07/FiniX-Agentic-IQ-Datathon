import pandas as pd

import src.finix.analytics as analytics


def test_integration_retains_chargeback_rows_and_flags_identity_mismatch(monkeypatch):
    monkeypatch.setattr(analytics, "write_csv", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(analytics, "write_report", lambda *_args, **_kwargs: None)
    transactions = pd.DataFrame(
        {
            "txn_id": ["TXN1"], "user_id": ["USR1"], "merchant_id": ["MCH1"], "amount": [100.0],
            "status": ["COMPLETED"], "timestamp": [pd.Timestamp("2026-01-01")],
        }
    )
    chargebacks = pd.DataFrame(
        {
            "complaint_id": ["CBK1", "CBK2"], "txn_id": ["TXN1", "TXN1"], "user_id": ["USR9", "USR9"], "merchant_id": ["MCH8", "MCH8"],
            "disputed_amount": [100.0, 10.0], "is_high_severity": [True, False], "disputed_amount_invalid_flag": [False, False],
            "reported_before_transaction_flag": [False, False], "bank_response_before_transaction_flag": [False, False],
        }
    )
    kyc = pd.DataFrame({"user_id": ["USR1"], "kyc_status": ["VERIFIED"], "risk_segment": ["LOW"], "is_kyc_rejected": [False], "is_high_kyc_risk": [False], "is_kyc_pending": [False], "monthly_income": [1000.0], "city": ["CITY"], "occupation": ["ROLE"], "pan_valid": [True], "aadhaar_valid": [True], "signup_timestamp": [pd.Timestamp("2025-01-01")]})
    merchants = pd.DataFrame({"merchant_id": ["MCH1"], "merchant_name": ["Merchant"], "merchant_category": ["RETAIL"], "business_type": ["SOLE"], "merchant_status": ["ACTIVE"], "mcc": ["5411"], "city": ["CITY"], "state": ["STATE"], "declared_avg_ticket_size": [100.0], "mcc_valid": [True], "is_suspended_merchant": [False]})
    result = analytics.integrate({"transactions": transactions, "chargebacks": chargebacks, "kyc": kyc, "merchants": merchants})
    linkage = result["chargeback_linkage"]
    assert len(linkage) == 2
    assert linkage["transaction_record_found"].all()
    assert linkage["identity_mismatch"].all()
    assert linkage["network_disconnected"].all()
    assert len(result["transactions"]) == 1
