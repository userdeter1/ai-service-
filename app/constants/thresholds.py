"""
Threshold Constants

Centralized threshold values used by algorithms and decision logic.

IMPORTANT: These values MUST stay in sync with algorithm implementations.
Do not modify without updating corresponding algorithm code.

Values are documented with SYNC comments showing which algorithm uses them.
"""

from typing import Optional

# ============================================================================
# Carrier Scoring Thresholds
# SYNC WITH: app/algorithms/carrier_scoring.py
# ============================================================================

# Tier classification thresholds (0-100 scale)
TIER_A_THRESHOLD = 85  # SYNC: carrier_scoring.py line 27 - Excellent carriers
TIER_B_THRESHOLD = 70  # SYNC: carrier_scoring.py line 28 - Good carriers
TIER_C_THRESHOLD = 50  # SYNC: carrier_scoring.py line 29 - Acceptable carriers
# Below TIER_C = Tier D (Needs Improvement)

# Used by slot recommender for buffer logic
LOW_CARRIER_SCORE_THRESHOLD = 60  # SYNC: slot_recommender.py line 28


# ============================================================================
# Slot Availability and Recommendation Thresholds
# SYNC WITH: app/algorithms/slot_recommender.py, app/agents/slot_agent.py
# ============================================================================

# Minimum capacity requirements
MIN_REMAINING_CAPACITY = 1  # SYNC: slot_recommender.py line 27 - Must have at least 1 spot

# Availability ratio for "low availability" warning
LOW_AVAILABILITY_RATIO = 0.3  # SYNC: slot_agent.py - Ratio below 0.3 triggers warning

# Time buffer for low-score carriers (minutes)
EARLY_BUFFER_MINUTES = 60  # SYNC: slot_recommender.py line 29 - 60min early for risky carriers


# ============================================================================
# Analytics and Stress Index Thresholds
# ============================================================================

# Stress index level thresholds (0-100 scale)
STRESS_LOW_MAX = 30       # Stress ≤ 30 = Low
STRESS_MEDIUM_MAX = 60    # 30 < Stress ≤ 60 = Medium  
STRESS_HIGH_MAX = 85      # 60 < Stress ≤ 85 = High
# Stress > 85 = Critical

# Capacity thresholds for proactive alerts
CRITICAL_CAPACITY_THRESHOLD = 0.90  # 90% utilization → critical alert
HIGH_CAPACITY_THRESHOLD = 0.75       # 75% utilization → high alert
MEDIUM_CAPACITY_THRESHOLD = 0.60     # 60% utilization → medium alert

# Anomaly thresholds for alerts
ANOMALY_SPIKE_THRESHOLD = 5          # >5 anomalies in window → alert
ANOMALY_SEVERITY_HIGH = 0.7          # Severity >= 0.7 → high priority


# ============================================================================
# Risk Classification Thresholds
# SYNC WITH: driver no-show risk heuristic (if implemented)
# ============================================================================

# Risk level thresholds (0-1 scale)
RISK_LOW_MAX = 0.3      # Risk <= 0.3 = Low
RISK_MEDIUM_MAX = 0.6   # 0.3 < Risk <= 0.6 = Medium
# Risk > 0.6 = High


# ============================================================================
# Helper Functions
# ============================================================================

def carrier_tier(score: float) -> str:
    """
    Determine carrier tier from score.
    
    Args:
        score: Carrier reliability score (0-100)
    
    Returns:
        Tier string: "A", "B", "C", or "D"
    
    Example:
        >>> carrier_tier(90)
        'A'
        >>> carrier_tier(75)
        'B'
        >>> carrier_tier(55)
        'C'
        >>> carrier_tier(40)
        'D'
    
    SYNC WITH: app/algorithms/carrier_scoring.py score_carrier()
    """
    if score >= TIER_A_THRESHOLD:
        return "A"
    elif score >= TIER_B_THRESHOLD:
        return "B"
    elif score >= TIER_C_THRESHOLD:
        return "C"
    else:
        return "D"


def risk_level(risk_score: float) -> str:
    """
    Determine risk level from score.
    
    Args:
        risk_score: Risk probability (0-1)
    
    Returns:
        Risk level string: "low", "medium", or "high"
    
    Example:
        >>> risk_level(0.2)
        'low'
        >>> risk_level(0.5)
        'medium'
        >>> risk_level(0.8)
        'high'
    """
    if risk_score <= RISK_LOW_MAX:
        return "low"
    elif risk_score <= RISK_MEDIUM_MAX:
        return "medium"
    else:
        return "high"


def is_low_carrier_score(score: float) -> bool:
    """
    Check if carrier score is low (needs buffer).
    
    Args:
        score: Carrier reliability score (0-100)
    
    Returns:
        True if score is below LOW_CARRIER_SCORE_THRESHOLD
    
    SYNC WITH: app/algorithms/slot_recommender.py recommend_slots()
    """
    return score < LOW_CARRIER_SCORE_THRESHOLD


def is_low_availability(available: int, total: int) -> bool:
    """
    Check if slot availability is low.
    
    Args:
        available: Number of available slots
        total: Total slot capacity
    
    Returns:
        True if availability ratio is below LOW_AVAILABILITY_RATIO
    
    Example:
        >>> is_low_availability(2, 10)
        True  # 0.2 < 0.3
        >>> is_low_availability(5, 10)
        False  # 0.5 >= 0.3
    """
    if total == 0:
        return True
    ratio = available / total
    return ratio < LOW_AVAILABILITY_RATIO
