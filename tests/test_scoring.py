import pandas as pd

from src.config import RULES
from src.scoring import score_transactions


def _create_scoring_input(
    **overrides: object,
) -> pd.DataFrame:
    transaction = {
        "transaction_id": "TX-001",
        "customer_id": "CUSTOMER-001",
        "amount_nok": 1_000.0,
        "amount_ratio_to_baseline": 1.0,
        "jurisdiction_risk": "low",
        "transactions_last_60m": 1,
        "is_new_counterparty": False,
    }

    transaction.update(overrides)

    return pd.DataFrame([transaction])


def test_transaction_triggering_all_rules_scores_100() -> None:
    transaction = _create_scoring_input(
        amount_nok=30_000,
        amount_ratio_to_baseline=5,
        jurisdiction_risk="high",
        transactions_last_60m=4,
        is_new_counterparty=True,
    )

    result = score_transactions(transaction).iloc[0]

    assert result["risk_score"] == 100
    assert result["risk_level"] == "High"


def test_normal_transaction_scores_zero() -> None:
    result = score_transactions(
        _create_scoring_input()
    ).iloc[0]

    assert result["risk_score"] == 0
    assert result["risk_level"] == "Low"
    assert result["triggered_rules"] == "None"


def test_score_65_is_high_priority() -> None:
    transaction = _create_scoring_input(
        amount_nok=30_000,
        amount_ratio_to_baseline=5,
        jurisdiction_risk="high",
    )

    result = score_transactions(transaction).iloc[0]

    assert result["risk_score"] == 65
    assert result["risk_level"] == "High"


def test_triggered_rules_lists_only_active_rules() -> None:
    transaction = _create_scoring_input(
        jurisdiction_risk="high",
    )

    result = score_transactions(transaction).iloc[0]

    assert result["triggered_rules"] == (
        RULES["high_risk_jurisdiction"]["label"]
    )