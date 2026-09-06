from __future__ import annotations

from collections.abc import Mapping
from html import escape

import pandas as pd
import streamlit as st

from src.config import RULES
from src.formatting import format_customer_id, format_nok, format_transaction_id, require_text


def filter_by_review_status(
    review_queue: pd.DataFrame, review_status: str, review_state: Mapping[str, object]
) -> pd.DataFrame:
    outcomes = review_queue["transaction_id"].map(
        lambda transaction_id: review_state.get(f"review_outcome_{transaction_id}", "Not reviewed")
    )
    if review_status == "Open cases":
        return review_queue.loc[outcomes.eq("Not reviewed")].copy()
    if review_status == "Reviewed cases":
        return review_queue.loc[
            outcomes.isin(["Expected activity", "Needs follow-up", "Escalate for further review"])
        ].copy()
    return review_queue.copy()


def get_review_state() -> dict[str, object]:
    review_state: dict[str, object] = {}

    for key in st.session_state:
        if key.startswith(("review_outcome_", "review_notes_")):
            review_state[key] = st.session_state[key]

    return review_state


def build_review_actions(transaction: pd.Series) -> list[str]:
    actions = []

    if transaction["rule_unusual_amount"]:
        actions.append(
            "Check the payment purpose against an invoice, agreement or other supporting document."
        )

    if transaction["rule_high_risk_country"]:
        actions.append(
            "Confirm why the payment has a high country-risk "
            "classification and whether it fits the customer's activity."
        )

    if transaction["rule_rapid_activity"]:
        actions.append(
            "Review the transactions from the same 60-minute period "
            "and check whether they share a recipient or purpose."
        )

    if transaction["rule_new_recipient"]:
        actions.append("Confirm who the recipient is and their relationship to the customer.")

    actions.append(
        "Record whether the activity is expected, needs follow-up or should be escalated."
    )

    return actions


def render_amount_comparison(transaction: pd.Series) -> None:
    amount_column, baseline_column, ratio_column = st.columns(3)

    amount_column.metric("Current amount", format_nok(transaction["amount_nok"]))
    baseline_column.metric("Previous median", format_nok(transaction["customer_median_amount"]))
    ratio_column.metric("Amount comparison", f"{transaction['amount_ratio_to_baseline']:.1f}x")


def render_rule_breakdown(transaction: pd.Series) -> None:
    risk_score = int(transaction["risk_score"])
    active_weights: list[int] = []

    st.markdown(f"### Why this case scored {risk_score}/100")

    if transaction["rule_unusual_amount"]:
        weight = RULES["unusual_amount"]["weight"]
        active_weights.append(weight)

        difference = transaction["amount_nok"] - transaction["customer_median_amount"]

        with st.container(border=True):
            st.markdown(f"#### Unusual amount · +{weight} points")

            render_amount_comparison(transaction)

            st.write(
                f"The payment is {format_nok(difference)} above the "
                "median of the customer's earlier transactions."
            )

            st.caption("Required: at least NOK 25,000 and at least 4.0 times the previous median.")

    if transaction["rule_high_risk_country"]:
        weight = RULES["high_risk_country"]["weight"]
        active_weights.append(weight)

        with st.container(border=True):
            st.markdown(f"#### High-risk country · +{weight} points")

            st.write("The transaction has a high country-risk classification.")

            st.caption("This is not an official country-risk assessment.")

    if transaction["rule_rapid_activity"]:
        weight = RULES["rapid_activity"]["weight"]
        active_weights.append(weight)

        transaction_count = int(transaction["transactions_last_60m"])

        with st.container(border=True):
            st.markdown(f"#### Rapid transaction activity · +{weight} points")

            st.write(
                f"The customer made {transaction_count} transactions "
                "within a rolling 60-minute period."
            )

            st.caption("Required: at least three transactions within 60 minutes.")

    if transaction["rule_new_recipient"]:
        weight = RULES["new_recipient"]["weight"]
        active_weights.append(weight)

        with st.container(border=True):
            st.markdown(f"#### New recipient · +{weight} points")

            render_amount_comparison(transaction)

            st.write(
                "This is the customer's first recorded outgoing transaction to this recipient."
            )

            st.caption(
                "Required: a new recipient, at least NOK 10,000 "
                "and at least twice the previous median."
            )

    calculation = " + ".join(str(weight) for weight in active_weights)

    risk_level = require_text(transaction["risk_level"], "risk_level")

    st.markdown(
        f"""
        <div class="trm-score-total trm-score-{risk_level.lower()}">
            <strong>{calculation} = {risk_score}/100</strong>
            <span>{risk_level} priority</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption("The score sets review priority and is not a probability of money laundering.")


def render_transaction_details(transaction: pd.Series) -> None:
    first_column, second_column, third_column = st.columns(3)

    first_column.write(f"**Transaction ID**  \n{transaction['transaction_id']}")
    first_column.write(f"**Customer ID**  \n{transaction['customer_id']}")
    first_column.write(f"**Time**  \n{transaction['timestamp']}")

    second_column.write(f"**Recipient**  \n{transaction['recipient_id']}")
    second_column.write(
        f"**New recipient**  \n{'Yes' if transaction['is_new_recipient'] else 'No'}"
    )
    second_column.write(f"**Country risk**  \n{transaction['country_risk'].title()}")

    channel = transaction["channel"].replace("_", " ").title()

    third_column.write(f"**Direction**  \n{transaction['direction'].title()}")
    third_column.write(f"**Channel**  \n{channel}")
    third_column.write(f"**Triggered flags**  \n{transaction['triggered_rules']}")


def save_review(transaction_id: str, next_transaction_id: str | None = None) -> None:
    st.session_state[f"review_outcome_{transaction_id}"] = st.session_state[
        f"review_outcome_widget_{transaction_id}"
    ]
    st.session_state[f"review_notes_{transaction_id}"] = st.session_state[
        f"review_notes_widget_{transaction_id}"
    ]
    if next_transaction_id is not None:
        st.session_state["active_case_id"] = next_transaction_id


def render_review_outcome(transaction_id: str, ordered_transaction_ids: list[str]) -> None:
    st.markdown("### Review outcome")

    outcome_key = f"review_outcome_{transaction_id}"
    notes_key = f"review_notes_{transaction_id}"

    outcome_widget_key = f"review_outcome_widget_{transaction_id}"
    notes_widget_key = f"review_notes_widget_{transaction_id}"

    # Dialog widgets are temporary. Review values are stored separately
    # so they remain available after the dialog closes.
    if outcome_widget_key not in st.session_state:
        st.session_state[outcome_widget_key] = st.session_state.get(outcome_key, "Not reviewed")

    if notes_widget_key not in st.session_state:
        st.session_state[notes_widget_key] = st.session_state.get(notes_key, "")

    st.selectbox(
        "Decision",
        options=[
            "Not reviewed",
            "Expected activity",
            "Needs follow-up",
            "Escalate for further review",
        ],
        key=outcome_widget_key,
    )

    st.text_area(
        "Review notes",
        placeholder=("Describe what was checked and the reason for the decision."),
        key=notes_widget_key,
        height=100,
    )

    position = ordered_transaction_ids.index(transaction_id)
    previous_column, save_column, next_column = st.columns(3)

    # Button callbacks save before the dialog reruns, so its new case loads immediately.
    previous_column.button(
        "Previous case",
        key=f"previous_case_{transaction_id}",
        disabled=position == 0,
        on_click=save_review,
        args=(transaction_id, ordered_transaction_ids[max(0, position - 1)]),
    )

    if save_column.button(
        "Save review",
        key=f"save_review_{transaction_id}",
        type="primary",
        on_click=save_review,
        args=(transaction_id,),
    ):
        # The full rerun refreshes the status-filtered queue and Excel export.
        st.rerun(scope="app")

    next_column.button(
        "Save and open next",
        key=f"next_case_{transaction_id}",
        disabled=position == len(ordered_transaction_ids) - 1,
        on_click=save_review,
        args=(
            transaction_id,
            ordered_transaction_ids[min(position + 1, len(ordered_transaction_ids) - 1)],
        ),
    )


def render_customer_activity(
    customer_id: str, all_transactions: pd.DataFrame, selected_transaction_id: str | None = None
) -> None:
    customer_transactions = all_transactions.loc[
        all_transactions["customer_id"] == customer_id
    ].sort_values(["timestamp", "transaction_id"], ascending=[False, False])

    flagged_transactions = customer_transactions.loc[customer_transactions["risk_score"] > 0]

    st.markdown(f"### {format_customer_id(customer_id)} activity")

    st.write(
        "Review the customer's history to decide whether a rule match requires further action."
    )
    st.caption("A rule match can still reflect normal customer activity.")

    metric_columns = st.columns(4)

    metric_columns[0].metric("Transactions", len(customer_transactions))
    metric_columns[1].metric(
        "Median amount", format_nok(customer_transactions["amount_nok"].median())
    )
    metric_columns[2].metric("Flagged transactions", len(flagged_transactions))
    metric_columns[3].metric(
        "Highest 60-minute count", int(customer_transactions["transactions_last_60m"].max())
    )

    activity_table = customer_transactions[
        [
            "transaction_id",
            "timestamp",
            "amount_nok",
            "recipient_id",
            "country_risk",
            "risk_score",
            "triggered_rules",
        ]
    ].copy()

    if selected_transaction_id is None:
        selected_case_labels = pd.Series("", index=activity_table.index, dtype="string")
    else:
        selected_case_labels = (
            activity_table["transaction_id"]
            .eq(selected_transaction_id)
            .map({True: "Current case", False: ""})
        )

    activity_table.insert(0, "selected", selected_case_labels)

    st.dataframe(
        activity_table,
        hide_index=True,
        width="stretch",
        height=390,
        column_config={
            "selected": "",
            "transaction_id": "Transaction ID",
            "timestamp": st.column_config.DatetimeColumn("Time", format="DD MMM YYYY, HH:mm"),
            "amount_nok": st.column_config.NumberColumn("Amount", format="NOK %.2f"),
            "recipient_id": "Recipient",
            "country_risk": "Country risk",
            "risk_score": st.column_config.NumberColumn("Score", format="%d/100"),
            "triggered_rules": "Flags",
        },
    )


@st.dialog("Case review", width="medium", on_dismiss="rerun")
def show_case_dialog(
    transaction_id: str, all_transactions: pd.DataFrame, ordered_transaction_ids: list[str]
) -> None:
    transaction_id = st.session_state.get("active_case_id", transaction_id)
    st.caption(
        f"Case {ordered_transaction_ids.index(transaction_id) + 1} of {len(ordered_transaction_ids)}"
    )
    matching_transactions = all_transactions.loc[
        all_transactions["transaction_id"] == transaction_id
    ]

    if matching_transactions.empty:
        st.error("The selected transaction could not be found.")
        return

    transaction = matching_transactions.iloc[0]

    customer_id = require_text(transaction["customer_id"], "customer_id")
    risk_level = require_text(transaction["risk_level"], "risk_level")

    st.markdown(
        f"""
        <div class="trm-dialog-heading">
            <div>
                <span class="trm-dialog-case">
                    {format_transaction_id(transaction_id)}
                </span>
                <span class="trm-priority-badge trm-{risk_level.lower()}">
                    {risk_level} priority
                </span>
            </div>
            <div class="trm-dialog-summary">
                {format_customer_id(customer_id)}
                · {format_nok(transaction["amount_nok"])}
                · {escape(str(transaction["triggered_rules"]))}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    review_tab, activity_tab = st.tabs(["Case review", "Customer activity"])

    with review_tab:
        render_rule_breakdown(transaction)

        st.markdown("### What to review")

        for action in build_review_actions(transaction):
            st.markdown(f"- {action}")

        with st.expander("Transaction details"):
            render_transaction_details(transaction)

        render_review_outcome(transaction_id, ordered_transaction_ids)

    with activity_tab:
        render_customer_activity(
            customer_id=customer_id,
            all_transactions=all_transactions,
            selected_transaction_id=transaction_id,
        )


@st.dialog("Customer activity", width="large")
def show_customer_dialog(customer_id: str, all_transactions: pd.DataFrame) -> None:
    render_customer_activity(customer_id=customer_id, all_transactions=all_transactions)
