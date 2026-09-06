from __future__ import annotations

from collections import deque
from datetime import timedelta

import pandas as pd

from src.config import INITIAL_CUSTOMER_BASELINE_NOK


def add_customer_risk_features(
    transactions: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compare each transaction with the customer's earlier activity.

    Only information available before the transaction is used when
    calculating the customer's normal amount.
    """
    result = transactions.copy()
    result["timestamp"] = pd.to_datetime(result["timestamp"])
    result["_original_order"] = range(len(result))

    result = result.sort_values(
        [
            "customer_id",
            "timestamp",
            "transaction_id",
        ]
    )

    baseline_parts: list[pd.Series] = []
    recent_count_parts: list[pd.Series] = []

    for _, customer_transactions in result.groupby("customer_id"):
        baseline_parts.append(
            _historical_amount_baseline(customer_transactions)
        )

        recent_count_parts.append(
            _count_transactions_in_60_minutes(
                customer_transactions["timestamp"]
            )
        )

    result["customer_median_amount"] = pd.concat(
        baseline_parts
    ).reindex(result.index)

    result["amount_ratio_to_baseline"] = (
        result["amount_nok"]
        / result["customer_median_amount"].clip(lower=1)
    )

    result["transactions_last_60m"] = (
        pd.concat(recent_count_parts)
        .reindex(result.index)
        .astype("int64")
    )

    # The dashboard displays the newest transactions first.
    return (
        result.sort_values(
            [
                "timestamp",
                "transaction_id",
            ],
            ascending=[
                False,
                False,
            ],
        )
        .drop(columns="_original_order")
        .reset_index(drop=True)
    )


def _historical_amount_baseline(
    customer_transactions: pd.DataFrame,
) -> pd.Series:
    """
    Calculate the median using only transactions from earlier timestamps.

    Transactions recorded at the same time receive the same baseline and
    cannot influence each other's result.
    """
    baseline_parts: list[pd.Series] = []
    historical_amounts: list[float] = []

    for _, same_time_transactions in customer_transactions.groupby(
        "timestamp",
        sort=True,
    ):
        if len(historical_amounts) >= 5:
            baseline = float(
                pd.Series(historical_amounts).median()
            )
        else:
            baseline = INITIAL_CUSTOMER_BASELINE_NOK

        baseline_parts.append(
            pd.Series(
                baseline,
                index=same_time_transactions.index,
                dtype="float64",
            )
        )

        historical_amounts.extend(
            same_time_transactions["amount_nok"].astype(float)
        )

    return pd.concat(baseline_parts).reindex(
        customer_transactions.index
    )


def _count_transactions_in_60_minutes(
    timestamps: pd.Series,
) -> pd.Series:
    timestamps_in_window: deque[pd.Timestamp] = deque()
    counts: list[int] = []
    window = timedelta(minutes=60)

    for timestamp in timestamps:
        while (
            timestamps_in_window
            and timestamp - timestamps_in_window[0] > window
        ):
            timestamps_in_window.popleft()

        timestamps_in_window.append(timestamp)
        counts.append(len(timestamps_in_window))

    return pd.Series(
        counts,
        index=timestamps.index,
        dtype="int64",
    )
