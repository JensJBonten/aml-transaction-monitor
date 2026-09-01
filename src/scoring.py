from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import RULES


def score_transactions(transactions: pd.DataFrame) -> pd.DataFrame:
    """
    AML rules run and return scored transactions.

    The score prioritises transactions for manual review.
    It is not a probability or proof of money laundering.
    """
    result = transactions.copy()

    # Transasctions of at least 25K nok are flagged and also 
    # when a transactino is four times higher than usual.
    result["rule_unusual_amount"] = (
        (result["amount_nok"] >= 25_000)
        & (result["amount_ratio_to_baseline"] >= 4)
    )

    result["rule_high_risk_jurisdiction"] = (
        result["jurisdiction_risk"] == "high"
    )

    result["rule_high_velocity"] = (
        result["transactions_last_60m"] >= 3
    )

    # A new counterparty alone is not enough to trigger the rule.
    result["rule_new_counterparty"] = (
        result["is_new_counterparty"]
        & (result["amount_nok"] >= 10_000)
        & (result["amount_ratio_to_baseline"] >= 2)
    )

    # Each rule is a separate boolean column that makes every
    # contribution visible in the dashboard and testable in isolation.
    result["risk_score"] = sum(
        result[f"rule_{rule_name}"].astype(int) * rule["weight"]
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


def _describe_triggered_rules(transaction: pd.Series) -> str:
    """Return readable labels for all rules triggered by a transaction."""
    triggered = [
        rule["label"]
        for rule_name, rule in RULES.items()
        if transaction[f"rule_{rule_name}"]
    ]

    return ", ".join(triggered) if triggered else "None"