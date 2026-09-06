INITIAL_CUSTOMER_BASELINE_NOK = 1_000.0

RULES = {
    "unusual_amount": {
        "label": "Unusual amount",
        "weight": 35,
    },
    "high_risk_country": {
        "label": "High-risk country",
        "weight": 30,
    },
    "rapid_activity": {
        "label": "Rapid transaction activity",
        "weight": 20,
    },
    "new_recipient": {
        "label": "New recipient",
        "weight": 15,
    },
}

RISK_LEVELS = ("Low", "Medium", "High")