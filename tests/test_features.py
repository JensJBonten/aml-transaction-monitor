import pandas as pd
import pytest

from src.data_generator import generate_transactions
from src.features import add_customer_risk_features
from src.scoring import score_transactions


def _create_transactions(
    timestamps: list[str],
    amounts: list[float] | None = None,
) -> pd.DataFrame:
    number_of_rows = len(timestamps)

    if amounts is None:
        amounts = [1_000.0] * number_of_rows

    return pd.DataFrame(
        {
            "transaction_id": [f"TX-{number:03d}" for number in range(1, number_of_rows + 1)],
            "customer_id": ["CUSTOMER-001"] * number_of_rows,
            "timestamp": pd.to_datetime(timestamps),
            "amount_nok": amounts,
            "direction": ["outgoing"] * number_of_rows,
            "counterparty_id": [f"CP-{number:03d}" for number in range(1, number_of_rows + 1)],
            "is_new_counterparty": [False] * number_of_rows,
            "jurisdiction_risk": ["low"] * number_of_rows,
            "channel": ["bank_transfer"] * number_of_rows,
        }
    )


def test_generator_is_deterministic_for_same_seed() -> None:
    first_dataset = generate_transactions(seed=42)
    second_dataset = generate_transactions(seed=42)

    pd.testing.assert_frame_equal(first_dataset, second_dataset)


def test_amount_ratio_uses_previous_customer_history() -> None:
    transactions = _create_transactions(
        timestamps=[
            "2026-08-01 10:00",
            "2026-08-02 10:00",
            "2026-08-03 10:00",
            "2026-08-04 10:00",
            "2026-08-05 10:00",
            "2026-08-06 10:00",
        ],
        amounts=[
            1_000,
            1_000,
            1_000,
            1_000,
            1_000,
            4_000,
        ],
    )

    result = add_customer_risk_features(transactions)
    latest_transaction = result.loc[result["transaction_id"] == "TX-006"].iloc[0]

    assert latest_transaction["customer_median_amount"] == 1_000
    assert latest_transaction["amount_ratio_to_baseline"] == 4


def test_current_transaction_does_not_affect_fallback_baseline() -> None:
    transactions = _create_transactions(
        timestamps=[
            "2026-08-01 10:00",
            "2026-08-02 10:00",
        ],
        amounts=[1_000, 25_000],
    )

    result = add_customer_risk_features(transactions)
    latest_transaction = result.loc[result["transaction_id"] == "TX-002"].iloc[0]

    assert latest_transaction["customer_median_amount"] == 1_000
    assert latest_transaction["amount_ratio_to_baseline"] == 25


def test_velocity_counts_transactions_inside_60_minute_window() -> None:
    transactions = _create_transactions(
        timestamps=[
            "2026-08-01 12:00",
            "2026-08-01 12:20",
            "2026-08-01 12:40",
        ]
    )

    result = add_customer_risk_features(transactions)
    counts = result.set_index("transaction_id")["transactions_last_60m"]

    assert counts["TX-001"] == 1
    assert counts["TX-002"] == 2
    assert counts["TX-003"] == 3


def test_transaction_after_60_minutes_starts_new_window() -> None:
    transactions = _create_transactions(
        timestamps=[
            "2026-08-01 12:00",
            "2026-08-01 13:01",
        ]
    )

    result = add_customer_risk_features(transactions)
    counts = result.set_index("transaction_id")["transactions_last_60m"]

    assert counts["TX-002"] == 1


@pytest.mark.parametrize(
    ("seed", "number_of_transactions"),
    [(48, 800), (93, 100)],
)
def test_injected_amount_scenarios_reliably_trigger(
    seed: int,
    number_of_transactions: int,
) -> None:
    transactions = generate_transactions(
        number_of_transactions=number_of_transactions,
        seed=seed,
    )
    result = score_transactions(add_customer_risk_features(transactions))

    unusual = result.loc[result["counterparty_id"] == "CP-901"].iloc[0]
    new_counterparty = result.loc[result["counterparty_id"] == "NEW-DEMO-001"].iloc[0]

    assert bool(unusual["rule_unusual_amount"])
    assert bool(new_counterparty["rule_new_counterparty"])


def test_velocity_demo_rows_do_not_trigger_jurisdiction_rule() -> None:
    result = score_transactions(add_customer_risk_features(generate_transactions()))
    velocity_rows = result.loc[
        result["counterparty_id"].isin(["CP-910", "CP-911", "CP-912", "CP-913"])
    ]
    jurisdiction_row = result.loc[result["counterparty_id"] == "CP-902"].iloc[0]

    assert len(velocity_rows) == 4
    assert not velocity_rows["rule_high_risk_jurisdiction"].any()
    assert bool(jurisdiction_row["rule_high_risk_jurisdiction"])
