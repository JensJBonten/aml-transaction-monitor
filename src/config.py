"""AML rule weights form a 100-point prioritisation score.
The score is not a probability that money laundering has occurred.
"""

RULES = {
 "unusual_amount": {"label": "Unusual amount", "weight": 35},
 "high_risk_jurisdiction": {
 "label": "High-risk jurisdiction", "weight": 30
 },
 "high_velocity": {
 "label": "High transaction velocity", "weight": 20
 },
 "new_counterparty": {
 "label": "New counterparty with elevated amount", "weight": 15
 },
}


RISK_LEVEL = ["Low", "Medium", "High"]
RISK_COLORS = { "Low" :  "#5D8A83", "Medium": "#F2B84B", "High": "#E05B5B" }