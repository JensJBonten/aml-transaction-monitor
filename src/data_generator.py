from __future__ import annotations

import numpy as np
import pandas as pd

from src.features import add_customer_risk_features

"""The data generated in this file is deterministic. Tests, riskscores and the dashboard are predictable this way"""


def generate_transactions(
    number_of_customers: int = 30,
    number_of_transactions: int = 800,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate synthetic transactions.

    Using the same seed to produces the same dataset every time for predicatiblity
    """

    if number_of_customers < 1:
        raise ValueError("number_of_customers must be at least 1")

    if number_of_transactions < 7:
        raise ValueError("number_of_transactions must be at least 7")

    rng = np.random.default_rng(seed)

    customer_ids = [f"CUSTOMER-{number:03d}" for number in range(1, number_of_customers + 1)]

    # Giving every customer an individual normal transaction level.
    baselines = {
        customer_id: float(rng.lognormal(mean=7.8, sigma=0.45)) for customer_id in customer_ids
    }

    # Use a fixed end date to ensure that the timestmaps remain deterministic.
    end = pd.Timestamp("2026-08-29 12:00:00")
    start = end - pd.Timedelta(days=30)

    # Reserving seven transactions for the known AML scenarios.
    base_transaction_count = number_of_transactions - 7

    # Randomly assign a customer to every ordinary transaction.
    selected_customers = rng.choice(
        customer_ids,
        size=base_transaction_count,
    )

    # Generate timestamps distributed across the 30-day period.
    timestamps = start + pd.to_timedelta(
        rng.integers(
            low=0,
            high=int((end - start).total_seconds()),
            size=base_transaction_count,
        ),
        unit="s",
    )

    # Generating an amount around a spesific costumers personal baseline
    # to give a more realistic transaction amount
    amounts = [
        round(
            baselines[customer_id] * float(rng.lognormal(mean=0, sigma=0.55)),
            2,
        )
        for customer_id in selected_customers
    ]

    # Around five percent of ordinary transactions use a new counterparty.
    new_counterparties = rng.random(base_transaction_count) < 0.05

    # Existing counterparties receive a normal synthetic ID.
    # New counterparties receive an ID starting with NEW.
    counterparty_ids = [
        (f"NEW-{index:04d}" if is_new else f"CP-{rng.integers(1, 81):03d}")
        for index, is_new in enumerate(new_counterparties, start=1)
    ]

    # Combining the generated values
    transactions = pd.DataFrame(
        {
            "customer_id": selected_customers,
            "timestamp": timestamps,
            "amount_nok": amounts,
            "direction": rng.choice(
                ["incoming", "outgoing"],
                size=base_transaction_count,
                p=[0.45, 0.55],
            ),
            "counterparty_id": counterparty_ids,
            "is_new_counterparty": new_counterparties,
            # Im using synthetic risk tiers, so not a real country list.
            "jurisdiction_risk": rng.choice(
                ["low", "medium", "high"],
                size=base_transaction_count,
                p=[0.80, 0.17, 0.03],
            ),
            "channel": rng.choice(
                ["bank_transfer", "card", "mobile"],
                size=base_transaction_count,
                p=[0.55, 0.30, 0.15],
            ),
        }
    )

    # Adding guaranteed examples of all four AML scenarios,
    # so that the Dashboard always has data.
    transactions = _inject_demo_scenarios(
        transactions=transactions,
        customer_ids=customer_ids,
        end=end,
    )

    # Sort chronologically before assigning transaction IDs.
    transactions = transactions.sort_values(
        ["timestamp", "customer_id"],
    ).reset_index(drop=True)

    # Insert stable and readable transaction IDs as the first column.
    transactions.insert(
        0,
        "transaction_id",
        [f"TX-{number:05d}" for number in range(1, len(transactions) + 1)],
    )

    return transactions


def _inject_demo_scenarios(
    transactions: pd.DataFrame,
    customer_ids: list[str],
    end: pd.Timestamp,
) -> pd.DataFrame:
    """
    Injecting guaranteed transactions representing the four AML rules.

    These transactions make the demo predictable even if the ordinary
    random transactions do not trigger every rule.
    """

    unusual_customer = customer_ids[0]
    jurisdiction_customer = customer_ids[min(1, len(customer_ids) - 1)]
    velocity_customer = customer_ids[min(2, len(customer_ids) - 1)]
    counterparty_customer = customer_ids[min(3, len(customer_ids) - 1)]

    unusual_row = {
        "customer_id": unusual_customer,
        "timestamp": end - pd.Timedelta(days=3),
        "amount_nok": 0.0,
        "direction": "outgoing",
        "counterparty_id": "CP-901",
        "is_new_counterparty": False,
        "jurisdiction_risk": "low",
        "channel": "bank_transfer",
    }
    unusual_baseline = _scenario_baseline(transactions, unusual_row)
    unusual_row["amount_nok"] = round(
        max(25_000, unusual_baseline * 5),
        2,
    )

    jurisdiction_row = {
        "customer_id": jurisdiction_customer,
        "timestamp": end - pd.Timedelta(days=2),
        "amount_nok": 4_500.00,
        "direction": "outgoing",
        "counterparty_id": "CP-902",
        "is_new_counterparty": False,
        "jurisdiction_risk": "high",
        "channel": "bank_transfer",
    }

    counterparty_row = {
        "customer_id": counterparty_customer,
        "timestamp": end - pd.Timedelta(days=1),
        "amount_nok": 0.0,
        "direction": "outgoing",
        "counterparty_id": "NEW-DEMO-001",
        "is_new_counterparty": True,
        "jurisdiction_risk": "low",
        "channel": "bank_transfer",
    }
    history_with_earlier_scenarios = pd.concat(
        [
            transactions,
            pd.DataFrame([unusual_row, jurisdiction_row]),
        ],
        ignore_index=True,
    )
    counterparty_baseline = _scenario_baseline(
        history_with_earlier_scenarios,
        counterparty_row,
    )
    counterparty_row["amount_nok"] = round(
        max(10_000, counterparty_baseline * 2.5),
        2,
    )

    demo_rows = [unusual_row, jurisdiction_row, counterparty_row]

    # Four transactions ten minutes apart that all occur inside a 60-min window
    velocity_start = end - pd.Timedelta(hours=2)

    for transaction_number in range(4):
        demo_rows.append(
            {
                "customer_id": velocity_customer,
                "timestamp": velocity_start + pd.Timedelta(minutes=transaction_number * 10),
                "amount_nok": 1_500.00,
                "direction": "outgoing",
                "counterparty_id": f"CP-{910 + transaction_number}",
                "is_new_counterparty": False,
                "jurisdiction_risk": "low",
                "channel": "mobile",
            }
        )

    # Add the seven scenario rows to the ordinary transactions.
    # ignore_index creates one continuous row index.
    return pd.concat(
        [transactions, pd.DataFrame(demo_rows)],
        ignore_index=True,
    )


def _scenario_baseline(
    transactions: pd.DataFrame,
    scenario: dict[str, object],
) -> float:
    """Return the production feature baseline for a candidate demo row."""
    candidate = pd.concat(
        [transactions, pd.DataFrame([scenario])],
        ignore_index=True,
    )
    featured = add_customer_risk_features(candidate)
    scenario_row = featured.loc[featured["counterparty_id"] == scenario["counterparty_id"]].iloc[0]
    return float(scenario_row["customer_median_amount"])
