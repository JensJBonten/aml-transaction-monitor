from __future__ import annotations

import pandas as pd
import streamlit as st

from src.case_review import filter_by_review_status, get_review_state, show_customer_dialog
from src.config import RISK_LEVELS
from src.dashboard import (
    build_sidebar_score_guide,
    render_metric_cards,
    render_queue_panel,
    reset_queue_page,
)
from src.data_generator import generate_transactions
from src.features import add_customer_risk_features
from src.formatting import format_customer_id, require_text
from src.scoring import score_transactions
from src.styles import apply_styles

st.set_page_config(page_title="Transaction Risk Monitor", layout="wide")

apply_styles()


@st.cache_data
def load_transactions() -> pd.DataFrame:
    # Streamlit reruns the script after each interaction. Caching avoids
    # rebuilding the same generated and scored dataset every time.
    transactions = generate_transactions()
    features = add_customer_risk_features(transactions)
    return score_transactions(features)


def clear_filters() -> None:
    st.session_state["filter_customer"] = "All customers"
    st.session_state["filter_priorities"] = list(RISK_LEVELS)
    st.session_state["filter_review_status"] = "Open cases"
    reset_queue_page()


transactions = load_transactions()

customer_options = ["All customers", *sorted(transactions["customer_id"].unique())]

st.sidebar.header("Filters")

selected_customer_option = st.sidebar.selectbox(
    "Customer",
    options=customer_options,
    format_func=lambda customer_id: (
        customer_id if customer_id == "All customers" else format_customer_id(customer_id)
    ),
    key="filter_customer",
    on_change=reset_queue_page,
)

selected_customer = require_text(selected_customer_option, "selected_customer")

selected_priorities = st.sidebar.multiselect(
    "Priority",
    options=RISK_LEVELS,
    default=list(RISK_LEVELS),
    key="filter_priorities",
    on_change=reset_queue_page,
)

selected_review_status = st.sidebar.selectbox(
    "Review status",
    options=["Open cases", "Reviewed cases", "All cases"],
    key="filter_review_status",
    on_change=reset_queue_page,
)

st.sidebar.button("Clear filters", on_click=clear_filters)

if selected_customer != "All customers" and st.sidebar.button(
    "View customer activity", width="stretch"
):
    show_customer_dialog(customer_id=selected_customer, all_transactions=transactions)

st.sidebar.markdown(build_sidebar_score_guide(), unsafe_allow_html=True)

if selected_customer == "All customers":
    scoped_transactions = transactions.copy()
else:
    scoped_transactions = transactions.loc[transactions["customer_id"] == selected_customer].copy()

all_flagged_transactions = scoped_transactions.loc[scoped_transactions["risk_score"] > 0].copy()

review_queue = all_flagged_transactions.loc[
    all_flagged_transactions["risk_level"].isin(selected_priorities)
].copy()

review_queue = review_queue.sort_values(
    ["risk_score", "timestamp", "transaction_id"], ascending=[False, False, False]
).reset_index(drop=True)
review_queue = filter_by_review_status(review_queue, selected_review_status, get_review_state())

st.title("Transaction Risk Monitor")

st.caption("This project uses generated demo data and simplified risk rules.")

render_metric_cards(
    scoped_transactions=scoped_transactions, flagged_transactions=all_flagged_transactions
)

st.markdown('<div class="trm-section-space"></div>', unsafe_allow_html=True)

render_queue_panel(review_queue, transactions)

st.caption(
    "A rule match starts a review. It is not a conclusion that the transaction is suspicious."
)
