from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.case_review import filter_by_review_status
from src.data_generator import generate_transactions
from src.export import build_excel_export
from src.features import add_customer_risk_features
from src.scoring import score_transactions


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("Open cases", ["TX-5", "TX-1"]),
        ("Reviewed cases", ["TX-3", "TX-2", "TX-4"]),
        ("All cases", ["TX-5", "TX-3", "TX-1", "TX-2", "TX-4"]),
    ],
)
def test_review_status_uses_saved_outcomes_and_preserves_order(status, expected):
    queue = pd.DataFrame({"transaction_id": ["TX-5", "TX-3", "TX-1", "TX-2", "TX-4"]})
    saved = {
        "review_outcome_TX-1": "Not reviewed",
        "review_outcome_TX-2": "Expected activity",
        "review_outcome_TX-3": "Needs follow-up",
        "review_outcome_TX-4": "Escalate for further review",
        "review_outcome_widget_TX-5": "Expected activity",
    }
    assert filter_by_review_status(queue, status, saved)["transaction_id"].tolist() == expected


def start_app():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
    app.run(timeout=20)
    assert not app.exception
    return app


def select_case(app, row=0):
    queue_key = next(
        key for key in app.session_state.filtered_state if key.startswith("review_queue_page_")
    )
    app.session_state[queue_key] = {"selection": {"cells": [(row, "Case")]}}
    app.run()
    assert not app.exception


def test_save_review_filters_queue_without_changing_kpis_and_exports_saved_values(monkeypatch):
    downloads = []

    def capture_export(queue, state):
        result = build_excel_export(queue, state)
        downloads.append(result)
        return result

    monkeypatch.setattr("src.dashboard.build_excel_export", capture_export)
    app = start_app()
    assert app.selectbox(key="filter_review_status").value == "Open cases"
    original_queue = app.dataframe[0].value.copy()
    original_kpis = [m.value for m in app.markdown if "trm-metric-card" in m.value]
    select_case(app)
    transaction_id = app.session_state["active_case_id"]
    app.selectbox(key=f"review_outcome_widget_{transaction_id}").select("Expected activity")
    app.text_area(key=f"review_notes_widget_{transaction_id}").input("Invoice checked.")
    app.button(key=f"save_review_{transaction_id}").click().run()
    assert not app.exception
    assert app.session_state[f"review_notes_{transaction_id}"] == "Invoice checked."
    assert original_queue.iloc[0]["Case"] not in app.dataframe[0].value["Case"].tolist()
    assert not any(c.value.startswith("Case 1 of") for c in app.caption)
    assert [m.value for m in app.markdown if "trm-metric-card" in m.value] == original_kpis

    app.selectbox(key="filter_review_status").select("Reviewed cases").run()
    assert app.dataframe[0].value["Case"].tolist() == [original_queue.iloc[0]["Case"]]
    exported = pd.read_excel(BytesIO(downloads[-1]))
    assert exported["Transaction ID"].tolist() == [transaction_id]
    assert exported["Review outcome"].tolist() == ["Expected activity"]
    assert exported["Review notes"].tolist() == ["Invoice checked."]

    app.selectbox(key="filter_review_status").select("All cases").run()
    assert app.dataframe[0].value.equals(original_queue)
    next(b for b in app.button if b.label == "Clear filters").click().run()
    assert app.selectbox(key="filter_review_status").value == "Open cases"
    assert app.session_state[f"review_outcome_{transaction_id}"] == "Expected activity"


def test_saving_not_reviewed_keeps_case_open():
    app = start_app()
    original_queue = app.dataframe[0].value.copy()
    select_case(app)
    transaction_id = app.session_state["active_case_id"]
    app.text_area(key=f"review_notes_widget_{transaction_id}").input("Still checking.")
    app.button(key=f"save_review_{transaction_id}").click().run()
    assert not app.exception
    assert app.dataframe[0].value.equals(original_queue)
    assert app.session_state[f"review_outcome_{transaction_id}"] == "Not reviewed"
    assert app.session_state[f"review_notes_{transaction_id}"] == "Still checking."


@pytest.mark.parametrize("status", ["Open cases", "Reviewed cases", "All cases"])
def test_selection_passes_full_status_filtered_order_across_queue_pages(monkeypatch, status):
    opened = []
    monkeypatch.setattr("src.dashboard.show_case_dialog", lambda **kwargs: opened.append(kwargs))
    transactions = score_transactions(add_customer_risk_features(generate_transactions()))
    queue = transactions.loc[transactions["risk_score"] > 0].sort_values(
        ["risk_score", "timestamp", "transaction_id"], ascending=[False, False, False]
    )
    app = start_app()
    saved = {
        f"review_outcome_{transaction_id}": "Needs follow-up"
        for transaction_id in queue["transaction_id"].iloc[: 2 if status == "Open cases" else 10]
    }
    for key, value in saved.items():
        app.session_state[key] = value
    app.selectbox(key="filter_review_status").select(status).run()
    expected = filter_by_review_status(queue, status, saved)["transaction_id"].tolist()
    select_case(app)
    assert opened[-1]["ordered_transaction_ids"] == expected
    assert opened[-1]["transaction_id"] == expected[0]
    app.button(key="queue_next").click().run()
    assert app.session_state["queue_page"] == 1
    select_case(app)
    assert opened[-1]["ordered_transaction_ids"] == expected
    assert opened[-1]["transaction_id"] == expected[8]
    app.button(key="queue_previous").click().run()
    assert app.session_state["queue_page"] == 0


def test_dialog_navigation_saves_both_directions_and_disables_boundaries():
    # Render the dialog on full test reruns too; real widget interactions rerun its fragment.
    app = AppTest.from_string("""
import streamlit as st
from src.case_review import show_case_dialog
from src.data_generator import generate_transactions
from src.features import add_customer_risk_features
from src.scoring import score_transactions

transactions = score_transactions(add_customer_risk_features(generate_transactions()))
queue = transactions.loc[transactions["risk_score"] > 0].sort_values(
    ["risk_score", "timestamp", "transaction_id"], ascending=[False, False, False]
)
ids = queue["transaction_id"].tolist()[:2]
st.session_state["test_ids"] = ids
show_case_dialog(ids[0], transactions, ids)
""").run(timeout=20)
    assert not app.exception
    first, second = app.session_state["test_ids"]
    assert any(c.value == "Case 1 of 2" for c in app.caption)
    assert app.button(key=f"previous_case_{first}").disabled
    app.selectbox(key=f"review_outcome_widget_{first}").select("Needs follow-up")
    app.text_area(key=f"review_notes_widget_{first}").input("Check recipient.")
    app.button(key=f"next_case_{first}").click().run()
    assert not app.exception
    assert any(c.value == "Case 2 of 2" for c in app.caption)
    assert app.button(key=f"next_case_{second}").disabled
    assert app.session_state[f"review_outcome_{first}"] == "Needs follow-up"
    assert app.session_state[f"review_notes_{first}"] == "Check recipient."
    app.selectbox(key=f"review_outcome_widget_{second}").select("Expected activity")
    app.text_area(key=f"review_notes_widget_{second}").input("Agreement checked.")
    app.button(key=f"previous_case_{second}").click().run()
    assert not app.exception
    assert any(c.value == "Case 1 of 2" for c in app.caption)
    assert app.session_state[f"review_outcome_{second}"] == "Expected activity"
    assert app.session_state[f"review_notes_{second}"] == "Agreement checked."
    assert app.text_area(key=f"review_notes_widget_{first}").value == "Check recipient."
