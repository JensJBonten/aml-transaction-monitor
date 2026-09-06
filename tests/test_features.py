import pandas as pd
from pandas.testing import assert_frame_equal

from src.data_generator import generate_transactions
from src.features import add_customer_risk_features
from src.scoring import score_transactions


def test_velocity_counts_transactions_in_60_minute_window() -> None:
    transactions = pd.DataFrame(
        {
            "transaction_id": [
                "TX-00001",
                "TX-00002",
                "TX-00003",
                "TX-00004",
            ],
            "customer_id": ["CUSTOMER-001"] * 4,
            "timestamp": pd.to_datetime(
                [
                    "2026-01-01 10:00:00",
                    "2026-01-01 10:20:00",
                    "2026-01-01 10:40:00",
                    "2026-01-01 11:41:00",
                ]
            ),
            "amount_nok": [1_000.0] * 4,
        }
    )

    result = add_customer_risk_features(transactions)
    result = result.set_index("transaction_id")

    assert result.loc["TX-00001", "transactions_last_60m"] == 1
    assert result.loc["TX-00002", "transactions_last_60m"] == 2
    assert result.loc["TX-00003", "transactions_last_60m"] == 3
    assert result.loc["TX-00004", "transactions_last_60m"] == 1


def test_amount_ratio_uses_previous_customer_history() -> None:
    transactions = pd.DataFrame(
        {
            "transaction_id": [
                "TX-00001",
                "TX-00002",
                "TX-00003",
                "TX-00004",
                "TX-00005",
                "TX-00006",
            ],
            "customer_id": ["CUSTOMER-001"] * 6,
            "timestamp": pd.date_range(
                start="2026-01-01",
                periods=6,
                freq="D",
            ),
            "amount_nok": [
                100.0,
                200.0,
                300.0,
                400.0,
                500.0,
                3_000.0,
            ],
        }
    )

    result = add_customer_risk_features(transactions)
    result = result.set_index("transaction_id")

    assert result.loc[
        "TX-00006",
        "customer_median_amount",
    ] == 300.0

    assert result.loc[
        "TX-00006",
        "amount_ratio_to_baseline",
    ] == 10.0


def test_transactions_at_same_time_do_not_affect_each_other() -> None:
    transactions = pd.DataFrame(
        {
            "transaction_id": [
                "TX-00001",
                "TX-00002",
                "TX-00003",
                "TX-00004",
                "TX-00005",
                "TX-00006",
                "TX-00007",
            ],
            "customer_id": ["CUSTOMER-001"] * 7,
            "timestamp": pd.to_datetime(
                [
                    "2026-01-01 10:00:00",
                    "2026-01-02 10:00:00",
                    "2026-01-03 10:00:00",
                    "2026-01-04 10:00:00",
                    "2026-01-05 10:00:00",
                    "2026-01-06 10:00:00",
                    "2026-01-06 10:00:00",
                ]
            ),
            "amount_nok": [
                1_000.0,
                1_000.0,
                1_000.0,
                1_000.0,
                1_000.0,
                1_000.0,
                100_000.0,
            ],
        }
    )

    result = add_customer_risk_features(transactions)
    result = result.set_index("transaction_id")

    assert result.loc[
        "TX-00006",
        "customer_median_amount",
    ] == 1_000.0

    assert result.loc[
        "TX-00007",
        "customer_median_amount",
    ] == 1_000.0


def test_same_timestamp_velocity_uses_transaction_id_order() -> None:
    transactions = pd.DataFrame(
        {
            "transaction_id": [
                "TX-00003",
                "TX-00001",
                "TX-00002",
            ],
            "customer_id": ["CUSTOMER-001"] * 3,
            "timestamp": pd.to_datetime(
                ["2026-01-01 10:00:00"] * 3
            ),
            "amount_nok": [1_000.0] * 3,
        }
    )

    result = add_customer_risk_features(transactions).set_index(
        "transaction_id"
    )

    assert result.loc["TX-00001", "transactions_last_60m"] == 1
    assert result.loc["TX-00002", "transactions_last_60m"] == 2
    assert result.loc["TX-00003", "transactions_last_60m"] == 3


def test_generator_is_deterministic_for_same_seed() -> None:
    first_result = generate_transactions(seed=42)
    second_result = generate_transactions(seed=42)

    assert_frame_equal(first_result, second_result)


def test_generator_returns_expected_columns_and_row_count() -> None:
    transactions = generate_transactions()

    expected_columns = [
        "transaction_id",
        "customer_id",
        "timestamp",
        "amount_nok",
        "direction",
        "recipient_id",
        "is_new_recipient",
        "country_risk",
        "channel",
    ]

    assert len(transactions) == 800
    assert transactions.columns.tolist() == expected_columns


def test_recipient_history_determines_is_new_recipient() -> None:
    transactions = generate_transactions()
    chronological = transactions.sort_values(
        ["customer_id", "timestamp", "transaction_id"]
    )

    expected = ~chronological.duplicated(
        subset=["customer_id", "recipient_id"],
        keep="first",
    )

    assert chronological["is_new_recipient"].tolist() == expected.tolist()

    controlled_new_recipient_rows = chronological.loc[
        chronological["recipient_id"].str.startswith("NEW-")
    ]
    assert controlled_new_recipient_rows["is_new_recipient"].all()


def test_demo_data_produces_varied_risk_scores() -> None:
    transactions = generate_transactions()
    features = add_customer_risk_features(transactions)
    scored_transactions = score_transactions(features)

    flagged_transactions = scored_transactions.loc[
        scored_transactions["risk_score"] > 0
    ]

    expected_scores = {
        15,
        20,
        30,
        35,
        50,
        65,
    }

    actual_scores = set(flagged_transactions["risk_score"])

    assert expected_scores.issubset(actual_scores)


def test_generated_demo_scenarios_produce_intended_scores() -> None:
    scored = score_transactions(
        add_customer_risk_features(generate_transactions())
    )

    expected_customer_scores = {
        "CUSTOMER-001": [65],
        "CUSTOMER-002": [30],
        "CUSTOMER-003": [35],
        "CUSTOMER-004": [35],
        "CUSTOMER-005": [35],
        "CUSTOMER-006": [15],
        "CUSTOMER-007": [15],
        "CUSTOMER-008": [50],
    }

    demo_rows = scored.loc[
        scored["timestamp"] > pd.Timestamp("2026-08-30 12:00:00")
    ]

    for customer_id, expected_scores in expected_customer_scores.items():
        actual_scores = demo_rows.loc[
            demo_rows["customer_id"] == customer_id,
            "risk_score",
        ].tolist()
        assert actual_scores == expected_scores

    assert sorted(
        demo_rows.loc[
            demo_rows["customer_id"] == "CUSTOMER-009",
            "risk_score",
        ]
    ) == [0, 0, 20, 50]
    assert sorted(
        demo_rows.loc[
            demo_rows["customer_id"] == "CUSTOMER-010",
            "risk_score",
        ]
    ) == [0, 0, 20, 35]


def test_country_risk_does_not_dominate_generated_alerts() -> None:
    transactions = generate_transactions()
    features = add_customer_risk_features(transactions)
    scored_transactions = score_transactions(features)

    flagged_transactions = scored_transactions.loc[
        scored_transactions["risk_score"] > 0
    ]

    high_country_count = int(
        flagged_transactions["rule_high_risk_country"].sum()
    )

    rule_columns = [
        "rule_unusual_amount",
        "rule_high_risk_country",
        "rule_rapid_activity",
        "rule_new_recipient",
    ]

    active_rule_counts = flagged_transactions[rule_columns].sum(axis=1)

    assert high_country_count < len(flagged_transactions) / 2
    assert (active_rule_counts >= 2).any()
