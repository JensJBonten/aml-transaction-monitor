from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

DEFAULT_BASELINE_AMOUNT = 1_000.0


def add_customer_risk_features(transactions: pd.DataFrame) -> pd.DataFrame:
    """
    Compare each transaction with the customer's previous behaviour.

    The function adds:
    - customer_median_amount
    - amount_ratio_to_baseline
    - transactions_last_60m
    """

    result = transactions.copy()
    result["timestamp"] = pd.to_datetime(result["timestamp"])

    # Feature calculations must happen chronologically, if not
    # transactions done in the future can influence earlier ones.
    result = result.sort_values(
        ["timestamp", "customer_id"],
        kind="mergesort",
    ).reset_index(drop=True)

    result["customer_median_amount"] = _historical_baselines(result)

    # Expresses amount relative to the customers historical baseline.
    result["amount_ratio_to_baseline"] = result["amount_nok"] / result[
        "customer_median_amount"
    ].clip(lower=1)

    result["transactions_last_60m"] = (
        result.groupby("customer_id")["timestamp"]
        .transform(_count_transactions_in_last_60_minutes)
        .astype(int)
    )

    result = result.sort_values(
        ["timestamp", "customer_id"],
        ascending=[False, True],
        kind="mergesort",
    ).reset_index(drop=True)

    return result


def _historical_baselines(transactions: pd.DataFrame) -> pd.Series:
    """Calculate baselines from transactions with an earlier timestamp."""
    baselines = pd.Series(index=transactions.index, dtype="float64")
    global_history: list[float] = []
    customer_history: defaultdict[str, list[float]] = defaultdict(list)

    # Rows sharing a timestamp are evaluated before any of their amounts are
    # added to history, so simultaneous transactions cannot affect each other.
    for _, timestamp_rows in transactions.groupby("timestamp", sort=False):
        for index, transaction in timestamp_rows.iterrows():
            previous_customer_amounts = customer_history[transaction["customer_id"]]

            if len(previous_customer_amounts) >= 5:
                baseline = float(np.median(previous_customer_amounts))
            elif global_history:
                baseline = float(np.median(global_history))
            else:
                baseline = DEFAULT_BASELINE_AMOUNT

            baselines.at[index] = baseline

        for _, transaction in timestamp_rows.iterrows():
            amount = transaction["amount_nok"]
            if pd.notna(amount):
                numeric_amount = float(amount)
                global_history.append(numeric_amount)
                customer_history[transaction["customer_id"]].append(numeric_amount)

    return baselines


def _count_transactions_in_last_60_minutes(
    timestamps: pd.Series,
) -> pd.Series:
    """
    Count transactions inside a rolling 60-minute window.

    `left` marks the oldest transaction still inside the window.
    `right` represents the transaction currently being evaluated.
    """

    counts: list[int] = []
    left = 0
    window = pd.Timedelta(minutes=60)

    for right, current_timestamp in enumerate(timestamps):
        # Moving the window start past transactions older than 60 min.
        while current_timestamp - timestamps.iloc[left] > window:
            left += 1
        # Invluide both the frist and current transaction in the count.
        counts.append(right - left + 1)

    return pd.Series(
        counts,
        index=timestamps.index,
        dtype="int64",
    )
