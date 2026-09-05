from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import RULES


def score_transactions(
    transactions: pd.DataFrame,
) -> pd.DataFrame:
    """
    Apply monitoring rules and calculate review-priority scores.

    Score determines which transactions should be reviewed first.
    It is not a probability or proof of money laundering.
    """
    result = transactions.copy()

    # Both conditions must be met. A large payment is not automatically
    # unusual if similar amounts are normal for the customer.
    result["rule_unusual_amount"] = (
        (result["amount_nok"] >= 25_000)
        & (result["amount_ratio_to_baseline"] >= 4)
    )

    result["rule_high_risk_country"] = (
        result["country_risk"] == "high"
    )

    result["rule_rapid_activity"] = (
        result["transactions_last_60m"] >= 3
    )

    # A new recipient alone is not enough to trigger the rule.
    result["rule_new_recipient"] = (
        (result["direction"] == "outgoing")
        & result["is_new_recipient"]
        & (result["amount_nok"] >= 10_000)
        & (result["amount_ratio_to_baseline"] >= 2)
    )

    # Keeping each rule in a separate column makes the score
    # explainable in the dashboard and testable in isolation.
    result["risk_score"] = sum(
        result[f"rule_{rule_name}"].astype(int)
        * rule["weight"]
        for rule_name, rule in RULES.items()
    )

    result["risk_level"] = np.select(
        [
            result["risk_score"] >= 60,
            result["risk_score"] >= 30,
        ],
        [
            "High",
            "Medium",
        ],
        default="Low",
    )

    result["triggered_rules"] = result.apply(
        _describe_triggered_rules,
        axis=1,
    )

    return result


def _describe_triggered_rules(
    transaction: pd.Series,
) -> str:
    """Return the labels of the rules triggered by a transaction."""
    triggered_rules = [
        rule["label"]
        for rule_name, rule in RULES.items()
        if transaction[f"rule_{rule_name}"]
    ]

    if not triggered_rules:
        return "None"

    return ", ".join(triggered_rules)
