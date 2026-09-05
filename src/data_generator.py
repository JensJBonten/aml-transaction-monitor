from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from src.config import INITIAL_CUSTOMER_BASELINE_NOK


def generate_transactions(
    number_of_customers: int = 30,
    number_of_transactions: int = 800,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate demo data."""
    if number_of_customers < 10:
        raise ValueError(
            "At least 10 customers are required for the demo scenarios."
        )

    if number_of_transactions < 40:
        raise ValueError("At least 40 transactions are required.")

    rng = np.random.default_rng(seed)

    customer_ids = [
        f"CUSTOMER-{number:03d}"
        for number in range(1, number_of_customers + 1)
    ]

    end = pd.Timestamp("2026-08-31 12:00:00")
    start = end - timedelta(days=30)

    # Sixteen controlled rows are added later. Subtracting them here
    # keeps the final dataset at exactly number_of_transactions rows.
    demo_row_count = 16
    base_transaction_count = number_of_transactions - demo_row_count

    # The final day is reserved for controlled scenarios. This prevents
    # random transactions from changing the intended 60 min time window.
    base_end = end - timedelta(days=1)

    timestamps = start + pd.to_timedelta(
        rng.integers(
            low=0,
            high=int((base_end - start).total_seconds()),
            size=base_transaction_count,
        ),
        unit="s",
    )

    # Each customer receives a different normal spending level.
    customer_baselines = pd.Series(
        rng.lognormal(
            mean=np.log(2_500),
            sigma=0.55,
            size=number_of_customers,
        ),
        index=customer_ids,
    )

    selected_customers = np.concatenate(
        [
            np.array(customer_ids[:10]),
            rng.choice(
                customer_ids,
                size=base_transaction_count - 10,
            ),
        ]
    )
    rng.shuffle(selected_customers)

    amounts = [
        customer_baselines[customer_id]
        * rng.lognormal(mean=0, sigma=0.45)
        for customer_id in selected_customers
    ]

    # High-risk values are reserved for controlled scenarios so that
    # the country rule does not dominate the review queue by chance.
    country_risks = rng.choice(
        ["low", "medium"],
        size=base_transaction_count,
        p=[0.90, 0.10],
    )

    base_transactions = pd.DataFrame(
        {
            "customer_id": selected_customers,
            "timestamp": timestamps,
            "amount_nok": np.round(amounts, 2),
            "direction": rng.choice(
                ["outgoing", "incoming"],
                size=base_transaction_count,
                p=[0.65, 0.35],
            ),
            "recipient_id": [
                f"RECIPIENT-{number:04d}"
                for number in rng.integers(
                    low=1,
                    high=301,
                    size=base_transaction_count,
                )
            ],
            # Calculated from chronological customer history after stable
            # transaction IDs have been assigned.
            "is_new_recipient": False,
            "country_risk": country_risks,
            "channel": rng.choice(
                [
                    "bank_transfer",
                    "card",
                    "mobile_payment",
                ],
                size=base_transaction_count,
                p=[0.55, 0.30, 0.15],
            ),
        }
    )

    demo_transactions = _build_demo_scenarios(
        base_transactions=base_transactions,
        customer_ids=customer_ids,
        end=end,
    )

    transactions = pd.concat(
        [
            base_transactions,
            demo_transactions,
        ],
        ignore_index=True,
    ).sort_values(
        "timestamp",
        kind="stable",
    )

    transactions.insert(
        0,
        "transaction_id",
        [
            f"TX-{number:05d}"
            for number in range(1, len(transactions) + 1)
        ],
    )

    transactions = _set_new_recipient_flags(transactions)

    return transactions.reset_index(drop=True)


def _set_new_recipient_flags(
    transactions: pd.DataFrame,
) -> pd.DataFrame:
    """Mark the first recipient occurrence in each customer's history."""
    result = transactions.copy()
    chronological = result.sort_values(
        [
            "customer_id",
            "timestamp",
            "transaction_id",
        ],
        kind="stable",
    )

    is_new_recipient = ~chronological.duplicated(
        subset=[
            "customer_id",
            "recipient_id",
        ],
        keep="first",
    )
    result.loc[chronological.index, "is_new_recipient"] = (
        is_new_recipient.to_numpy()
    )

    return result


def _build_demo_scenarios(
    base_transactions: pd.DataFrame,
    customer_ids: list[str],
    end: pd.Timestamp,
) -> pd.DataFrame:
    """
    Add controlled cases that trigger individual rules and combinations.

    The cases are intentionally not distributed equally. They provide
    enough variation to demonstrate how several rule matches increase
    the review-priority score.
    """
    baselines = {
        customer_id: _customer_baseline(
            transactions=base_transactions,
            customer_id=customer_id,
        )
        for customer_id in customer_ids[:10]
    }
    existing_recipients = {
        customer_id: str(
            base_transactions.loc[
                base_transactions["customer_id"] == customer_id,
                "recipient_id",
            ].iloc[0]
        )
        for customer_id in customer_ids[:10]
    }

    def normal_amount(customer_id: str) -> float:
        return round(
            max(
                500,
                baselines[customer_id] * 0.9,
            ),
            2,
        )

    def unusual_amount(customer_id: str) -> float:
        return round(
            max(
                25_000,
                baselines[customer_id] * 5,
            ),
            2,
        )

    def new_recipient_amount(customer_id: str) -> float:
        return round(
            max(
                10_000,
                baselines[customer_id] * 2.5,
            ),
            2,
        )

    rows = [
        # Unusual amount and high country risk: 65 points.
        _demo_row(
            customer_id=customer_ids[0],
            timestamp=end - timedelta(hours=11),
            amount_nok=unusual_amount(customer_ids[0]),
            recipient_id=existing_recipients[customer_ids[0]],
            is_new_recipient=False,
            country_risk="high",
        ),
        # High country risk only: 30 points.
        _demo_row(
            customer_id=customer_ids[1],
            timestamp=end - timedelta(hours=10),
            amount_nok=normal_amount(customer_ids[1]),
            recipient_id=existing_recipients[customer_ids[1]],
            is_new_recipient=False,
            country_risk="high",
        ),
    ]

    # Three unusual-amount cases create several medium-priority examples.
    for offset, customer_id in zip(
        [9, 8, 7],
        customer_ids[2:5],
        strict=True,
    ):
        rows.append(
            _demo_row(
                customer_id=customer_id,
                timestamp=end - timedelta(hours=offset),
                amount_nok=unusual_amount(customer_id),
                recipient_id=existing_recipients[customer_id],
                is_new_recipient=False,
                country_risk="low",
            )
        )

    # Two new-recipient cases trigger the 15-point rule by itself.
    for offset, customer_id in zip(
        [6, 5],
        customer_ids[5:7],
        strict=True,
    ):
        rows.append(
            _demo_row(
                customer_id=customer_id,
                timestamp=end - timedelta(hours=offset),
                amount_nok=new_recipient_amount(customer_id),
                recipient_id=f"NEW-RECIPIENT-{customer_id[-3:]}",
                is_new_recipient=True,
                country_risk="low",
            )
        )

    # This case combines unusual amount and new recipient: 50 points.
    rows.append(
        _demo_row(
            customer_id=customer_ids[7],
            timestamp=end - timedelta(hours=4),
            amount_nok=unusual_amount(customer_ids[7]),
            recipient_id="NEW-RECIPIENT-008",
            is_new_recipient=True,
            country_risk="low",
        )
    )

    # The third and fourth transactions activate rapid activity.
    # The fourth also has high country risk, producing a higher score.
    first_burst_start = end - timedelta(hours=3)

    for position in range(4):
        is_last = position == 3

        rows.append(
            _demo_row(
                customer_id=customer_ids[8],
                timestamp=(
                    first_burst_start
                    + timedelta(minutes=position * 10)
                ),
                amount_nok=normal_amount(customer_ids[8]),
                recipient_id=existing_recipients[customer_ids[8]],
                is_new_recipient=False,
                country_risk="high" if is_last else "low",
            )
        )

    # The fourth transaction in this group combines rapid activity
    # with a new recipient.
    second_burst_start = end - timedelta(hours=1)

    for position in range(4):
        is_last = position == 3

        rows.append(
            _demo_row(
                customer_id=customer_ids[9],
                timestamp=(
                    second_burst_start
                    + timedelta(minutes=position * 10)
                ),
                amount_nok=(
                    new_recipient_amount(customer_ids[9])
                    if is_last
                    else normal_amount(customer_ids[9])
                ),
                recipient_id=(
                    "NEW-RECIPIENT-RAPID"
                    if is_last
                    else existing_recipients[customer_ids[9]]
                ),
                is_new_recipient=is_last,
                country_risk="low",
            )
        )

    return pd.DataFrame(rows)


def _customer_baseline(
    transactions: pd.DataFrame,
    customer_id: str,
) -> float:
    """Return the customer's median from the generated transactions."""
    customer_amounts = transactions.loc[
        transactions["customer_id"] == customer_id,
        "amount_nok",
    ]

    if len(customer_amounts) < 5:
        return INITIAL_CUSTOMER_BASELINE_NOK

    return float(customer_amounts.median())


def _demo_row(
    customer_id: str,
    timestamp: pd.Timestamp,
    amount_nok: float,
    recipient_id: str,
    is_new_recipient: bool,
    country_risk: str,
) -> dict[str, object]:
    """Build one controlled outgoing demo transaction."""
    return {
        "customer_id": customer_id,
        "timestamp": timestamp,
        "amount_nok": amount_nok,
        "direction": "outgoing",
        "recipient_id": recipient_id,
        "is_new_recipient": is_new_recipient,
        "country_risk": country_risk,
        "channel": "bank_transfer",
    }
