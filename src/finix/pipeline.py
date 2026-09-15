"""Command-line orchestration for the complete reproducible FiniX pipeline."""
from __future__ import annotations

import json
import traceback
from datetime import UTC, datetime

import pandas as pd

from .analytics import build_risk_marts, engineer_features, integrate
from .cleaning import clean_all
from .core import REPORTS_DIR
from .network import build_network
from .validation import validate_cleaned


def run_pipeline() -> dict[str, object]:
    """Run cleaning, validation, features, integration, risk, and network layers."""
    cleaned = clean_all()
    validation = validate_cleaned(cleaned)
    hard_failures = validation.loc[validation["status"].eq("FAIL")]
    if not hard_failures.empty:
        failed_checks = "; ".join(hard_failures["check"].tolist())
        raise ValueError(f"Validation failed before feature engineering: {failed_checks}")
    features = engineer_features(cleaned)
    integrated = integrate(features)
    risk = build_risk_marts(integrated)
    network = build_network(integrated["transactions"], integrated["chargeback_linkage"], risk["users"], risk["merchants"])

    run_summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "cleaned_rows": {name: len(result.frame) for name, result in cleaned.items()},
        "validation_checks": len(validation),
        "validation_warnings": int(validation["status"].eq("WARN").sum()),
        "chargeback_linkage_rows": len(integrated["chargeback_linkage"]),
        "transaction_intelligence_rows": len(integrated["transactions"]),
        "user_risk_rows": len(risk["users"]),
        "merchant_risk_rows": len(risk["merchants"]),
        "network_nodes": len(network["nodes"]),
        "network_edges": len(network["edges"]),
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "pipeline_run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
    return {"summary": run_summary, "validation": validation, "features": features, "integrated": integrated, "risk": risk, "network": network}


def main() -> None:
    """Run the pipeline and print compact, judge-friendly audit figures."""
    try:
        result = run_pipeline()
    except Exception as error:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        (REPORTS_DIR / "pipeline_failure.log").write_text(traceback.format_exc(), encoding="utf-8")
        print(f"FiniX pipeline failed: {error}")
        raise
    summary = result["summary"]
    print("FiniX pipeline completed")
    for key, value in summary.items():
        print(f"{key}: {value}")
    warnings = result["validation"].loc[result["validation"]["status"].eq("WARN"), ["dataset", "check", "numerator", "denominator", "percentage"]]
    if not warnings.empty:
        print("\nValidation warnings (data-quality findings retained):")
        print(warnings.to_string(index=False))


if __name__ == "__main__":
    main()
