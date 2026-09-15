from src.finix.cleaning import clean_chargebacks, clean_transactions


def test_chargeback_cleaning_preserves_row_level_audit_and_removes_only_exact_duplicates():
    result = clean_chargebacks()
    assert len(result.frame) == 2800
    assert result.frame.duplicated().sum() == 0
    assert result.frame["complaint_id"].is_unique
    assert (result.frame["disputed_amount"].dropna() >= 0).all()
    assert {"numerator", "denominator", "percentage"}.issubset(result.audit.columns)


def test_transaction_cleaning_produces_unique_transaction_keys():
    result = clean_transactions()
    nonmissing = result.frame.loc[result.frame["txn_id"].notna(), "txn_id"]
    assert len(result.frame) == 20000
    assert nonmissing.is_unique
    assert set(result.frame["status"].dropna().unique()).issubset({"COMPLETED", "FAILED", "PENDING"})
