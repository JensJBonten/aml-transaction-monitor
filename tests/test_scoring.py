import pandas as pd

from src.scoring import score_transactions


def build_transaction(
    *,
    amount_nok: float = 1_000.0,
    amount_ratio_to_baseline: float = 1.0,
    country_risk: str = "low",
    transactions_last_60m: int = 1,
    is_new_recipient: bool = False,
    direction: str = "outgoing",
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "amount_nok": [amount_nok],
            "amount_ratio_to_baseline": [
                amount_ratio_to_baseline
            ],
            "country_risk": [country_risk],
            "transactions_last_60m": [
                transactions_last_60m
            ],
            "is_new_recipient": [is_new_recipient],
            "direction": [direction],
        }
    )


def test_transaction_triggering_all_rules_scores_100() -> None:
    transaction = build_transaction(
        amount_nok=50_000.0,
        amount_ratio_to_baseline=5.0,
        country_risk="high",
        transactions_last_60m=3,
        is_new_recipient=True,
    )

    result = score_transactions(transaction).iloc[0]

    assert result["risk_score"] == 100
    assert result["risk_level"] == "High"
    assert result["rule_unusual_amount"]
    assert result["rule_high_risk_country"]
    assert result["rule_rapid_activity"]
    assert result["rule_new_recipient"]


def test_normal_transaction_scores_zero() -> None:
    transaction = build_transaction()

    result = score_transactions(transaction).iloc[0]

    assert result["risk_score"] == 0
    assert result["risk_level"] == "Low"
    assert result["triggered_rules"] == "None"


def test_score_65_is_high_priority() -> None:
    transaction = build_transaction(
        amount_nok=25_000.0,
        amount_ratio_to_baseline=4.0,
        country_risk="high",
    )

    result = score_transactions(transaction).iloc[0]

    assert result["risk_score"] == 65
    assert result["risk_level"] == "High"


def test_score_30_is_medium_priority() -> None:
    transaction = build_transaction(
        country_risk="high",
    )

    result = score_transactions(transaction).iloc[0]

    assert result["risk_score"] == 30
    assert result["risk_level"] == "Medium"


def test_triggered_rules_lists_only_active_rules() -> None:
    transaction = build_transaction(
        amount_nok=12_000.0,
        amount_ratio_to_baseline=2.5,
        transactions_last_60m=3,
        is_new_recipient=True,
    )

    result = score_transactions(transaction).iloc[0]

    assert result["risk_score"] == 35
    assert result["risk_level"] == "Medium"
    assert (
        result["triggered_rules"]
        == "Rapid transaction activity, New recipient"
    )
    assert not result["rule_unusual_amount"]
    assert not result["rule_high_risk_country"]
    assert result["rule_rapid_activity"]
    assert result["rule_new_recipient"]


def test_incoming_transaction_cannot_trigger_new_recipient_rule() -> None:
    transaction = build_transaction(
        amount_nok=12_000.0,
        amount_ratio_to_baseline=2.5,
        is_new_recipient=True,
        direction="incoming",
    )

    result = score_transactions(transaction).iloc[0]

    assert not result["rule_new_recipient"]
    assert result["risk_score"] == 0
