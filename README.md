# Transaction Risk Monitor

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://transaction-risk-monitor.streamlit.app/)

A small Streamlit project for reviewing generated transaction data.

The application checks transactions against a set of simple risk rules and places matching transactions in a review queue. Each case shows which rules were triggered and how the score was calculated.

## Features

- Generated demo data for 30 customers
- Customer-specific amount baselines
- Transaction activity within a 60-minute window
- Explainable rule-based scoring
- Filters for customer, priority and review status
- Case review with customer transaction history
- Review outcomes and notes
- Excel export
- Automated tests with GitHub Actions

## Scoring

Scores are additions of triggered rules.

| Rule | Points |
|---|---:|
| Unusual amount | 35 |
| High-risk country | 30 |
| Rapid transaction activity | 20 |
| New recipient | 15 |

Priority levels:

- Low: 0–29 points
- Medium: 30–59 points
- High: 60–100 points

The score helps decide which transactions should be reviewed first. It is not a probability of money laundering.

## Data processing

```text
Generated data → Customer features → Risk scoring → Review queue
```

Customer baselines use only earlier transactions. This means the transaction being checked does not affect its own baseline.

The generated data also contains a few controlled cases to make sure every rule can be demonstrated.

## Run the project

Create and activate a virtual environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the dependencies:

```powershell
python -m pip install -r requirements-dev.txt
```

Start the dashboard:

```powershell
streamlit run app.py
```

## Tests

```powershell
pytest -q
ruff check .
```

The same checks run automatically through GitHub Actions.

## Limitations

This is a demo project using generated data and simplified risk rules. It does not use real customer information or an official country-risk list.

Review outcomes and notes are stored only for the current Streamlit session. The application does not include a database, login or user management.
