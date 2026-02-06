"""
Algorithms Package

Provides deterministic scoring and recommendation algorithms:
- carrier_scoring: Carrier reliability scoring (0-100) with weighted components
- slot_recommender: Slot recommendation with availability and carrier-based ranking

All algorithms use deterministic calculations (no randomness) and return structured results.
"""

from app.algorithms.carrier_scoring import score_carrier
from app.algorithms.slot_recommender import recommend_slots

__all__ = [
    "score_carrier",
    "recommend_slots"
]
