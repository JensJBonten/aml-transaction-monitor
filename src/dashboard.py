from __future__ import annotations

from hashlib import sha256
from html import escape

import pandas as pd
import streamlit as st

from src.case_review import get_review_state, show_case_dialog
from src.config import RULES
from src.export import build_excel_export
from src.formatting import format_nok, format_transaction_id, require_text

CASES_PER_PAGE = 8
PRIORITY_COLORS = {"High": "#ff6262", "Medium": "#f2b84b", "Low": "#74c77b"}


def reset_queue_page() -> None:
    st.session_state["queue_page"] = 0
    st.session_state.pop("handled_queue_selection", None)


def build_sidebar_score_guide() -> str:
    rule_rows = "".join(
        (
            '<div class="trm-sidebar-rule">'
            f"<span>{escape(rule['label'])}</span>"
            f"<strong>+{rule['weight']}</strong>"
            "</div>"
        )
        for rule in RULES.values()
    )

    return (
        '<div class="trm-sidebar-guide">'
        "<h3>How scoring works</h3>"
        '<div class="trm-sidebar-label">Scoring rules</div>'
        f'<div class="trm-sidebar-rules">{rule_rows}</div>'
        '<div class="trm-sidebar-label trm-threshold-heading">'
        "Priority levels"
        "</div>"
        '<div class="trm-sidebar-thresholds">'
        '<div><span class="trm-dot trm-dot-low"></span>'
        "<span>Low</span><strong>0–29</strong></div>"
        '<div><span class="trm-dot trm-dot-medium"></span>'
        "<span>Medium</span><strong>30–59</strong></div>"
        '<div><span class="trm-dot trm-dot-high"></span>'
        "<span>High</span><strong>60–100</strong></div>"
        "</div>"
        '<p class="trm-sidebar-note">'
        "Scores are additions of triggered rules."
        "</p>"
        "</div>"
    )


def render_metric_card(label: str, value: int, accent: str) -> None:
    st.markdown(
        f"""
        <div class="trm-metric-card trm-metric-{accent}">
            <div class="trm-metric-accent"></div>
            <div>
                <div class="trm-metric-label">{escape(label)}</div>
                <div class="trm-metric-value">{value:,}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_cards(
    scoped_transactions: pd.DataFrame, flagged_transactions: pd.DataFrame
) -> None:
    metric_columns = st.columns(3)

    with metric_columns[0]:
        render_metric_card("Transactions checked", len(scoped_transactions), "blue")

    with metric_columns[1]:
        render_metric_card("Flagged for review", len(flagged_transactions), "yellow")

    with metric_columns[2]:
        high_priority_count = int((flagged_transactions["risk_level"] == "High").sum())

        render_metric_card("High-priority cases", high_priority_count, "red")


def style_priority(priority: object) -> str:
    color = PRIORITY_COLORS.get(str(priority), PRIORITY_COLORS["Low"])
    return f"color: {color}; font-weight: 700"


def style_case(row: pd.Series) -> list[str]:
    color = PRIORITY_COLORS.get(str(row["Priority"]), "#9eacc0")

    return [
        f"color: {color}" if column == "Case" else ""
        for column in row.index
    ]


def style_score(score: object) -> str:
    try:
        numeric_score = int(str(score).split("/")[0])
    except ValueError:
        return ""

    priority = "High" if numeric_score >= 60 else "Medium" if numeric_score >= 30 else "Low"
    return style_priority(priority)


def build_queue_table(visible_cases: pd.DataFrame) -> pd.DataFrame:
    queue_table = pd.DataFrame(
        {
            "Case": [
                f"● {format_transaction_id(require_text(transaction_id, 'transaction_id'))}"
                for transaction_id in visible_cases["transaction_id"]
            ],
            "Amount": [format_nok(amount) for amount in visible_cases["amount_nok"]],
            "Score": [f"{int(score)}/100" for score in visible_cases["risk_score"]],
            "Priority": visible_cases["risk_level"].to_numpy(),
            "Key flags": visible_cases["triggered_rules"].to_numpy(),
        }
    )

    return queue_table


def render_review_queue(review_queue: pd.DataFrame, all_transactions: pd.DataFrame) -> None:
    if review_queue.empty:
        st.info("No transactions match the selected filters.")
        return

    page_count = max(1, (len(review_queue) + CASES_PER_PAGE - 1) // CASES_PER_PAGE)

    stored_page = st.session_state.get("queue_page", 0)

    if isinstance(stored_page, int):
        current_page = min(stored_page, page_count - 1)
    else:
        current_page = 0

    st.session_state["queue_page"] = current_page

    page_start = current_page * CASES_PER_PAGE
    page_end = page_start + CASES_PER_PAGE

    visible_cases = review_queue.iloc[page_start:page_end].reset_index(drop=True)
    ordered_transaction_ids = review_queue["transaction_id"].tolist()
    # A changed queue must not reuse a cell selection belonging to another case.
    queue_signature = sha256("\n".join(ordered_transaction_ids).encode()).hexdigest()

    queue_table = build_queue_table(visible_cases)

    styled_queue = (
        queue_table.style.apply(style_case, axis=1)
        .map(style_score, subset=["Score"])
        .map(style_priority, subset=["Priority"])
    )

    selection_event = st.dataframe(
        styled_queue,
        hide_index=True,
        width="stretch",
        height=322,
        key=f"review_queue_page_{current_page}_{queue_signature}",
        on_select="rerun",
        selection_mode="single-cell",
        column_config={
            "Case": st.column_config.TextColumn("Case", width="small"),
            "Amount": st.column_config.TextColumn("Amount", width="small"),
            "Score": st.column_config.TextColumn("Score", width="small"),
            "Priority": st.column_config.TextColumn("Priority", width="small"),
            "Key flags": st.column_config.TextColumn("Key flags", width="large"),
        },
    )

    handle_queue_selection(
        selection_event.selection.cells,
        visible_cases,
        current_page,
        all_transactions,
        ordered_transaction_ids,
    )
    render_pagination(current_page, page_count)

    st.caption(
        f"Showing {page_start + 1}–{min(page_end, len(review_queue))} of {len(review_queue)} cases."
    )


def render_queue_panel(review_queue: pd.DataFrame, all_transactions: pd.DataFrame) -> None:
    with st.container(border=True):
        heading_column, export_column = st.columns([3, 1], vertical_alignment="bottom")

        with heading_column:
            st.subheader("Review queue")
            st.caption("Select a case to review it.")

        with export_column:
            st.download_button(
                "Export cases to Excel",
                data=build_excel_export(review_queue, get_review_state()),
                file_name="transaction_review_cases.xlsx",
                mime=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                width="stretch",
                disabled=review_queue.empty,
            )

        render_review_queue(review_queue=review_queue, all_transactions=all_transactions)


def handle_queue_selection(
    selected_cells: list[tuple[int, str]],
    visible_cases: pd.DataFrame,
    current_page: int,
    all_transactions: pd.DataFrame,
    ordered_transaction_ids: list[str],
) -> None:
    if selected_cells:
        selected_position, selected_column = selected_cells[0]

        selected_transaction_id = require_text(
            visible_cases.iloc[selected_position]["transaction_id"], "transaction_id"
        )

        selection_token = f"{current_page}:{selected_transaction_id}:{selected_column}"

        # A full rerun retains the cell selection; do not reopen a handled dialog.
        if st.session_state.get("handled_queue_selection") != selection_token:
            st.session_state["handled_queue_selection"] = selection_token
            st.session_state["active_case_id"] = selected_transaction_id

            show_case_dialog(
                transaction_id=selected_transaction_id,
                all_transactions=all_transactions,
                ordered_transaction_ids=ordered_transaction_ids,
            )
    else:
        st.session_state.pop("handled_queue_selection", None)


def render_pagination(current_page: int, page_count: int) -> None:
    if page_count > 1:
        previous_column, page_column, next_column = st.columns([1, 2, 1])

        if previous_column.button(
            "Previous", key="queue_previous", disabled=current_page == 0, width="stretch"
        ):
            change_queue_page(current_page - 1)

        page_column.markdown(
            f"""
            <div class="trm-page-count">
                Page {current_page + 1} of {page_count}
            </div>
            """,
            unsafe_allow_html=True,
        )

        if next_column.button(
            "Next", key="queue_next", disabled=current_page == page_count - 1, width="stretch"
        ):
            change_queue_page(current_page + 1)


def change_queue_page(page: int) -> None:
    reset_queue_page()
    st.session_state["queue_page"] = page
    st.rerun()
