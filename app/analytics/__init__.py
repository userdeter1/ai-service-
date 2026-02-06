"""
Analytics Package

Provides advanced analytics features for smart port operations:
- Stress Index: Real-time congestion/pressure scoring (0-100)
- Proactive Alerts: Automated operational alerts
- What-If Simulations: Scenario modeling for decision support

All features use REAL backend data when available with graceful MVP fallback.
"""

from app.analytics.stress_index import compute_stress_index, stress_level
from app.analytics.proactive_alerts import generate_alerts, alert_severity_score
from app.analytics.what_if_simulation import simulate_scenario

__all__ = [
    "compute_stress_index",
    "stress_level",
    "generate_alerts",
    "alert_severity_score",
    "simulate_scenario"
]
