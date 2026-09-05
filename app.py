from __future__ import annotations

from html import escape
from io import BytesIO

import pandas as pd
import streamlit as st

from src.config import RISK_LEVELS, RULES
from src.data_generator import generate_transactions
from src.features import add_customer_risk_features
from src.scoring import score_transactions
from src.styles import apply_styles

CASES_PER_PAGE = 8

st.set_page_config(
    page_title="Transaction Risk Monitor",
    layout="wide",
)

apply_styles()


@st.cache_data
def load_transactions() -> pd.DataFrame:
    # Streamlit reruns the script after every interaction. Caching avoids
    # rebuilding the same generated and scored dataset each time.
    transactions = generate_transactions()
    features = add_customer_risk_features(transactions)
    return score_transactions(features)


def require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")

    return value

def format_transaction_id(transaction_id: str) -> str:
    number = int(transaction_id.split("-")[-1])
    return f"Case {number}"


def format_customer_id(customer_id: str) -> str:
    number = int(customer_id.split("-")[-1])
    return f"Customer {number:03d}"


def format_nok(amount: float, decimals: int = 0) -> str:
    return f"NOK {amount:,.{decimals}f}"


def build_review_actions(transaction: pd.Series) -> list[str]:
    actions = []

    if transaction["rule_unusual_amount"]:
        actions.append(
            "Check the payment purpose against an invoice, agreement "
            "or other supporting document."
        )

    if transaction["rule_high_risk_country"]:
        actions.append(
            "Confirm why the payment has a high country-risk "
            "classification and whether it fits the customer's activity."
        )

    if transaction["rule_rapid_activity"]:
        actions.append(
            "Review the transactions made during the same 60-minute "
            "period and check whether they share a recipient or purpose."
        )

    if transaction["rule_new_recipient"]:
        actions.append(
            "Confirm who the recipient is and their relationship "
            "to the customer."
        )

    actions.append(
        "Record whether the activity is expected, needs follow-up "
        "or should be escalated."
    )

    return actions


def render_rule_breakdown(transaction: pd.Series) -> None:
    risk_score = int(transaction["risk_score"])

    st.markdown(f"### Why this case scored {risk_score}/100")

    active_weights: list[int] = []

    if transaction["rule_unusual_amount"]:
        weight = RULES["unusual_amount"]["weight"]
        active_weights.append(weight)

        difference = (
            transaction["amount_nok"]
            - transaction["customer_median_amount"]
        )

        with st.container(border=True):
            st.markdown(f"#### Unusual amount · +{weight} points")

            amount_column, baseline_column, ratio_column = st.columns(3)

            amount_column.metric(
                "Current amount",
                format_nok(transaction["amount_nok"]),
            )

            baseline_column.metric(
                "Previous median",
                format_nok(transaction["customer_median_amount"]),
            )

            ratio_column.metric(
                "Compared with previous median",
                f"{transaction['amount_ratio_to_baseline']:.1f}x",
            )

            st.write(
                f"The payment is {format_nok(difference)} above the "
                "customer's median across earlier transactions."
            )

            st.caption(
                "This rule requires an amount of at least NOK 25,000 "
                "and at least 4.0 times the previous median. "
                "Both conditions were met."
            )

    if transaction["rule_high_risk_country"]:
        weight = RULES["high_risk_country"]["weight"]
        active_weights.append(weight)

        with st.container(border=True):
            st.markdown(f"#### High-risk country · +{weight} points")

            st.metric(
                "Country risk",
                transaction["country_risk"].title(),
            )

            st.write(
                "The transaction has a high country-risk classification "
                "in the generated demo data."
            )

            st.caption(
                "The classification demonstrates the rule and is not "
                "an official country-risk assessment."
            )

    if transaction["rule_rapid_activity"]:
        weight = RULES["rapid_activity"]["weight"]
        active_weights.append(weight)

        with st.container(border=True):
            st.markdown(
                f"#### Rapid transaction activity · +{weight} points"
            )

            st.metric(
                "Transactions within 60 minutes",
                int(transaction["transactions_last_60m"]),
            )

            st.write(
                "The customer made at least three transactions "
                "within a rolling 60-minute period."
            )

            st.caption(
                "This identifies activity that should be reviewed. "
                "It does not determine whether the activity is unusual "
                "for the customer."
            )

    if transaction["rule_new_recipient"]:
        weight = RULES["new_recipient"]["weight"]
        active_weights.append(weight)

        with st.container(border=True):
            st.markdown(f"#### New recipient · +{weight} points")

            amount_column, ratio_column = st.columns(2)

            amount_column.metric(
                "Current amount",
                format_nok(transaction["amount_nok"]),
            )

            ratio_column.metric(
                "Compared with previous median",
                f"{transaction['amount_ratio_to_baseline']:.1f}x",
            )

            st.write(
                "This is the customer's first transaction "
                "with the recipient."
            )

            st.caption(
                "This rule also requires an amount of at least "
                "NOK 10,000 and at least twice the previous median. "
                "All conditions were met."
            )

    calculation = " + ".join(str(weight) for weight in active_weights)
    risk_level = require_text(
        transaction["risk_level"],
        "risk_level",
    )

    st.markdown(
        f"""
        <div class="trm-score-total">
            {calculation} = {risk_score}/100 · {risk_level} priority
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        "The score is the sum of triggered rule points. "
        "It sets review priority and is not a probability "
        "of money laundering."
    )


def render_transaction_details(transaction: pd.Series) -> None:
    st.markdown("### Transaction details")

    first_column, second_column, third_column = st.columns(3)

    first_column.write(
        f"**Transaction ID**  \n"
        f"{transaction['transaction_id']}"
    )
    first_column.write(
        f"**Customer ID**  \n"
        f"{transaction['customer_id']}"
    )
    first_column.write(
        f"**Time**  \n"
        f"{transaction['timestamp']}"
    )

    second_column.write(
        f"**Recipient**  \n"
        f"{transaction['recipient_id']}"
    )
    second_column.write(
        f"**New recipient**  \n"
        f"{'Yes' if transaction['is_new_recipient'] else 'No'}"
    )
    second_column.write(
        f"**Country risk**  \n"
        f"{transaction['country_risk'].title()}"
    )

    third_column.write(
        f"**Direction**  \n"
        f"{transaction['direction'].title()}"
    )

    channel = transaction["channel"].replace("_", " ").title()

    third_column.write(f"**Channel**  \n{channel}")
    third_column.write(
        f"**Triggered flags**  \n"
        f"{transaction['triggered_rules']}"
    )


def render_review_outcome(transaction_id: str) -> None:
    st.markdown("### Review outcome")

    outcome_key = f"review_outcome_{transaction_id}"
    notes_key = f"review_notes_{transaction_id}"

    outcome_widget_key = f"review_outcome_widget_{transaction_id}"
    notes_widget_key = f"review_notes_widget_{transaction_id}"

    # Dialog widgets are temporary. Review values are stored separately
    # so they remain available after the dialog closes.
    if outcome_widget_key not in st.session_state:
        st.session_state[outcome_widget_key] = (
            st.session_state.get(
                outcome_key,
                "Not reviewed",
            )
        )

    if notes_widget_key not in st.session_state:
        st.session_state[notes_widget_key] = (
            st.session_state.get(
                notes_key,
                "",
            )
        )

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
        placeholder=(
            "Describe what was checked and the reason for the decision."
        ),
        key=notes_widget_key,
    )

    st.caption(
        "The outcome is entered by the reviewer and does not change "
        "the calculated risk score."
    )

    if st.button(
        "Save review",
        key=f"save_review_{transaction_id}",
        type="primary",
    ):
        st.session_state[outcome_key] = (
            st.session_state[outcome_widget_key]
        )
        st.session_state[notes_key] = (
            st.session_state[notes_widget_key]
        )

        # The full rerun rebuilds the Excel export with saved values.
        st.rerun(scope="app")


def render_customer_activity(
    customer_id: str,
    all_transactions: pd.DataFrame,
    selected_transaction_id: str | None = None,
) -> None:
    # The complete history provides context, but the reviewer decides
    # whether the activity is expected or requires further action.
    customer_transactions = all_transactions.loc[
        all_transactions["customer_id"] == customer_id
    ].sort_values(
        "timestamp",
        ascending=False,
    )

    flagged_transactions = customer_transactions.loc[
        customer_transactions["risk_score"] > 0
    ]

    st.markdown(f"### {format_customer_id(customer_id)} activity")

    st.write(
        "Review the complete customer history before deciding "
        "whether a rule match requires further action."
    )

    metric_columns = st.columns(4)

    metric_columns[0].metric(
        "Transactions",
        len(customer_transactions),
    )

    metric_columns[1].metric(
        "Median amount",
        format_nok(
            customer_transactions["amount_nok"].median()
        ),
    )

    metric_columns[2].metric(
        "Flagged transactions",
        len(flagged_transactions),
    )

    metric_columns[3].metric(
        "Highest 60-minute count",
        int(
            customer_transactions[
                "transactions_last_60m"
            ].max()
        ),
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
        selected_case_labels = pd.Series(
            "",
            index=activity_table.index,
            dtype="string",
        )
    else:
        selected_case_labels = (
            activity_table["transaction_id"]
            .eq(selected_transaction_id)
            .map(
                {
                    True: "Current case",
                    False: "",
                }
            )
        )

    activity_table.insert(
        0,
        "selected",
        selected_case_labels,
    )

    st.dataframe(
        activity_table,
        hide_index=True,
        width="stretch",
        height=420,
        column_config={
            "selected": "",
            "transaction_id": "Transaction ID",
            "timestamp": st.column_config.DatetimeColumn(
                "Time",
                format="DD MMM YYYY, HH:mm",
            ),
            "amount_nok": st.column_config.NumberColumn(
                "Amount",
                format="NOK %.2f",
            ),
            "recipient_id": "Recipient",
            "country_risk": "Country risk",
            "risk_score": st.column_config.NumberColumn(
                "Score",
                format="%d/100",
            ),
            "triggered_rules": "Flags",
        },
    )

    st.info(
        "Rapid transaction activity uses a fixed 60-minute threshold. "
        "A rule match can still represent normal customer activity, "
        "which is why the full history is available for manual review."
    )


@st.dialog("Case review", width="large")
def show_case_dialog(
    transaction_id: str,
    all_transactions: pd.DataFrame,
) -> None:
    transaction = all_transactions.loc[
        all_transactions["transaction_id"] == transaction_id
    ].iloc[0]

    customer_id = require_text(
        transaction["customer_id"],
        "customer_id",
    )
    risk_level = require_text(
        transaction["risk_level"],
        "risk_level",
    )

    st.markdown(
        f"## {format_transaction_id(transaction_id)} "
        f"· {risk_level} priority"
    )

    st.write(
        f"{format_customer_id(customer_id)} · "
        f"{format_nok(transaction['amount_nok'])} · "
        f"{transaction['triggered_rules']}"
    )

    review_tab, activity_tab = st.tabs(
        [
            "Case review",
            "Customer activity",
        ]
    )

    with review_tab:
        render_rule_breakdown(transaction)

        st.markdown("### What to review")

        for action in build_review_actions(transaction):
            st.markdown(f"- {action}")

        render_transaction_details(transaction)
        render_review_outcome(transaction_id)

    with activity_tab:
        render_customer_activity(
            customer_id=customer_id,
            all_transactions=all_transactions,
            selected_transaction_id=transaction_id,
        )


@st.dialog("Customer activity", width="large")
def show_customer_dialog(
    customer_id: str,
    all_transactions: pd.DataFrame,
) -> None:
    render_customer_activity(
        customer_id=customer_id,
        all_transactions=all_transactions,
    )


def build_excel_export(review_queue: pd.DataFrame) -> bytes:
    case_columns = review_queue[
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

    case_columns["review_outcome"] = [
        st.session_state.get(
            f"review_outcome_{transaction_id}",
            "Not reviewed",
        )
        for transaction_id in case_columns["transaction_id"]
    ]

    case_columns["review_notes"] = [
        st.session_state.get(
            f"review_notes_{transaction_id}",
            "",
        )
        for transaction_id in case_columns["transaction_id"]
    ]

    case_columns.columns = [
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
        [
            {
                "Rule": rule["label"],
                "Points": rule["weight"],
            }
            for rule in RULES.values()
        ]
    )

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        case_columns.to_excel(
            writer,
            sheet_name="Review cases",
            index=False,
        )
        scoring_rules.to_excel(
            writer,
            sheet_name="Scoring rules",
            index=False,
        )

    return output.getvalue()


def build_score_guide() -> str:
    rule_items = "".join(
        (
            '<div class="trm-rule-item">'
            f"<span>{escape(rule['label'])}</span>"
            f"<strong>+{rule['weight']}</strong>"
            "</div>"
        )
        for rule in RULES.values()
    )

    return (
        '<div class="trm-score-guide">'
        '<div class="trm-guide-heading">How scoring works</div>'
        f'<div class="trm-rule-grid">{rule_items}</div>'
        '<div class="trm-thresholds">'
        "Low: 0–29 · Medium: 30–59 · High: 60–100. "
        "Scores are additions of triggered rules, not probabilities."
        "</div>"
        "</div>"
    )


transactions = load_transactions()

st.title("Transaction Risk Monitor")

st.write(
    "Checks generated transaction data, prioritises rule matches "
    "and explains what should be reviewed."
)

st.caption(
    "Portfolio demo using generated demo data. Risk classifications "
    "and scoring thresholds are simplified examples."
)

st.sidebar.header("Filters")

customer_options = [
    "All customers",
    *sorted(transactions["customer_id"].unique()),
]

selected_customer_option = st.sidebar.selectbox(
    "Customer",
    options=customer_options,
    format_func=lambda customer_id: (
        customer_id
        if customer_id == "All customers"
        else format_customer_id(customer_id)
    ),
)

selected_customer = require_text(
    selected_customer_option,
    "selected_customer",
)

selected_priorities = st.sidebar.multiselect(
    "Priority",
    options=RISK_LEVELS,
    default=list(RISK_LEVELS),
)

minimum_score = st.sidebar.slider(
    "Minimum score",
    min_value=0,
    max_value=100,
    value=0,
    step=5,
)

if (
    selected_customer != "All customers"
    and st.sidebar.button(
        "See all customer transactions",
        width="stretch",
    )
):
    show_customer_dialog(
        customer_id=selected_customer,
        all_transactions=transactions,
    )

if selected_customer == "All customers":
    scoped_transactions = transactions.copy()
else:
    scoped_transactions = transactions.loc[
        transactions["customer_id"] == selected_customer
    ].copy()

all_flagged_transactions = scoped_transactions.loc[
    scoped_transactions["risk_score"] > 0
].copy()

review_queue = all_flagged_transactions.loc[
    all_flagged_transactions["risk_level"].isin(
        selected_priorities
    )
    & (
        all_flagged_transactions["risk_score"]
        >= minimum_score
    )
].sort_values(
    [
        "risk_score",
        "timestamp",
    ],
    ascending=[
        False,
        False,
    ],
)

metric_columns = st.columns(3)

metric_columns[0].metric(
    "Transactions checked",
    len(scoped_transactions),
)

metric_columns[1].metric(
    "Flagged for review",
    len(all_flagged_transactions),
)

metric_columns[2].metric(
    "High-priority cases",
    int(
        (
            all_flagged_transactions["risk_level"]
            == "High"
        ).sum()
    ),
)

st.markdown(
    build_score_guide(),
    unsafe_allow_html=True,
)

heading_column, export_column = st.columns(
    [
        3,
        1,
    ]
)

with heading_column:
    st.subheader("Transactions to review")

    st.caption(
        "Highest score first. Select a case to see the calculation "
        "and customer history."
    )

with export_column:
    st.download_button(
        "Export cases to Excel",
        data=build_excel_export(review_queue),
        file_name="transaction_review_cases.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        width="stretch",
        disabled=review_queue.empty,
    )

if review_queue.empty:
    st.info("No transactions match the selected filters.")

else:
    page_count = max(
        1,
        (
            len(review_queue)
            + CASES_PER_PAGE
            - 1
        )
        // CASES_PER_PAGE,
    )

    current_page = min(
        st.session_state.get(
            "queue_page",
            0,
        ),
        page_count - 1,
    )

    st.session_state["queue_page"] = current_page

    page_start = current_page * CASES_PER_PAGE
    page_end = page_start + CASES_PER_PAGE

    visible_cases = review_queue.iloc[
        page_start:page_end
    ]

    for _, transaction in visible_cases.iterrows():
        transaction_id = require_text(
            transaction["transaction_id"],
            "transaction_id",
        )
        risk_level = require_text(
            transaction["risk_level"],
            "risk_level",
        )

        row_label = (
            f"**{format_transaction_id(transaction_id)}** "
            f"· {risk_level} "
            f"· {int(transaction['risk_score'])}/100 points "
            f"· {format_nok(transaction['amount_nok'])}  \n"
            f"{transaction['triggered_rules']}"
        )

        if st.button(
            row_label,
            key=f"case_{risk_level.lower()}_{transaction_id}",
            width="stretch",
        ):
            show_case_dialog(
                transaction_id=transaction_id,
                all_transactions=transactions,
            )

    if page_count > 1:
        previous_column, page_column, next_column = st.columns(
            [
                1,
                2,
                1,
            ]
        )

        if previous_column.button(
            "Previous",
            disabled=current_page == 0,
            width="stretch",
        ):
            st.session_state["queue_page"] = current_page - 1
            st.rerun()

        page_column.markdown(
            f"""
            <div class="trm-page-count">
                Page {current_page + 1} of {page_count}
            </div>
            """,
            unsafe_allow_html=True,
        )

        if next_column.button(
            "Next",
            disabled=current_page == page_count - 1,
            width="stretch",
        ):
            st.session_state["queue_page"] = current_page + 1
            st.rerun()

st.caption(
    "A rule match starts a review. It is not a conclusion "
    "that the transaction is suspicious."
)
