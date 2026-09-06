from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO

import pandas as pd

from src.config import RULES


def build_excel_export(review_queue: pd.DataFrame, review_state: Mapping[str, object]) -> bytes:
    case_data = review_queue[
        [
            "transaction_id",
            "customer_id",
            "timestamp",
            "amount_nok",
            "recipient_id",
            "country_risk",
            "risk_score",
            "risk_level",
            "triggered_rules",
        ]
    ].copy()

    for field, default in (("review_outcome", "Not reviewed"), ("review_notes", "")):
        case_data[field] = pd.Series(
            [
                review_state.get(f"{field}_{transaction_id}", default)
                for transaction_id in case_data["transaction_id"]
            ],
            index=case_data.index,
            dtype="string",
        )

    case_data.columns = [
        "Transaction ID",
        "Customer ID",
        "Time",
        "Amount NOK",
        "Recipient ID",
        "Country risk",
        "Score",
        "Priority",
        "Flags",
        "Review outcome",
        "Review notes",
    ]

    scoring_rules = pd.DataFrame(
        [{"Rule": rule["label"], "Points": rule["weight"]} for rule in RULES.values()]
    )

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        case_data.to_excel(writer, sheet_name="Review cases", index=False)

        scoring_rules.to_excel(writer, sheet_name="Scoring rules", index=False)

    return output.getvalue()
