"""
Carrier Scoring Algorithm

Deterministic algorithm to score carrier reliability and performance.
Produces a score (0-100), tier (A/B/C/D), components breakdown, and reasons.

No external dependencies or randomness - purely based on statistics.
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# ============================================================================
# Scoring Configuration
# ============================================================================

# Weight distribution for score components (must sum to 1.0)
WEIGHT_COMPLETION_RATE = 0.30
WEIGHT_ON_TIME_PERFORMANCE = 0.25
WEIGHT_NO_SHOW_PENALTY = 0.20
WEIGHT_ANOMALY_PENALTY = 0.15
WEIGHT_DWELL_EFFICIENCY = 0.10

# Thresholds for tier classification
TIER_A_THRESHOLD = 85  # Excellent
TIER_B_THRESHOLD = 70  # Good
TIER_C_THRESHOLD = 50  # Acceptable
# Below TIER_C = Tier D (Needs Improvement)

# Confidence thresholds based on sample size
HIGH_CONFIDENCE_BOOKINGS = 50
LOW_CONFIDENCE_BOOKINGS = 10

# Performance targets
TARGET_COMPLETION_RATE = 0.95  # 95%
TARGET_ON_TIME_RATE = 0.90     # 90%
MAX_ACCEPTABLE_NO_SHOW_RATE = 0.05  # 5%
MAX_ACCEPTABLE_ANOMALY_RATE = 0.10  # 10%
TARGET_DWELL_MINUTES = 45.0    # Efficient dwell time


# ============================================================================
# Scoring Functions
# ============================================================================


def score_carrier(stats: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score a carrier based on performance statistics.
    
    Args:
        stats: Carrier statistics dict.
    
    Returns:
        Dict with score, tier, components, reasons, confidence, stats_summary.
    """
    total = stats.get("total_bookings", 0)
    completed = stats.get("completed_bookings", 0)
    cancelled = stats.get("cancelled_bookings", 0)
    no_shows = stats.get("no_shows", 0)
    late_arrivals = stats.get("late_arrivals", 0)
    avg_delay = stats.get("avg_delay_minutes", 0.0)
    avg_dwell = stats.get("avg_dwell_minutes", 0.0)
    anomaly_count = stats.get("anomaly_count", 0)
    
    # Handle edge case: no bookings
    if total == 0:
        return {
            "score": 0.0,
            "tier": "D",
            "components": {},
            "reasons": ["No booking history available for this carrier"],
            "confidence": 0.0,
            "stats_summary": {"total_bookings": 0}
        }
    
    # Calculate rates
    completion_rate = completed / total
    no_show_rate = no_shows / total
    late_rate = late_arrivals / total if completed > 0 else 0.0
    anomaly_rate = anomaly_count / total
    
    # Calculate component scores (0-100 each)
    components = {}
    
    # 1. Completion Rate (30%)
    completion_score = min(100, (completion_rate / TARGET_COMPLETION_RATE) * 100)
    components["completion"] = round(completion_score, 2)
    
    # 2. On-Time Performance (25%)
    # Penalize based on late arrivals and average delay
    on_time_rate = 1.0 - late_rate
    delay_penalty = min(20, avg_delay / 3.0)  # Max 20 points penalty for delays
    on_time_score = max(0, min(100, (on_time_rate / TARGET_ON_TIME_RATE) * 100 - delay_penalty))
    components["on_time"] = round(on_time_score, 2)
    
    # 3. No-Show Penalty (20%)
    # Lower is better
    no_show_score = max(0, 100 - (no_show_rate / MAX_ACCEPTABLE_NO_SHOW_RATE) * 100)
    components["no_show"] = round(no_show_score, 2)
    
    # 4. Anomaly Penalty (15%)
    # Lower is better
    anomaly_score = max(0, 100 - (anomaly_rate / MAX_ACCEPTABLE_ANOMALY_RATE) * 100)
    components["anomaly"] = round(anomaly_score, 2)
    
    # 5. Dwell Efficiency (10%)
    # Closer to target is better
    if avg_dwell > 0:
        dwell_diff = abs(avg_dwell - TARGET_DWELL_MINUTES)
        dwell_score = max(0, 100 - (dwell_diff / TARGET_DWELL_MINUTES) * 100)
    else:
        dwell_score = 50  # Neutral if no dwell time data
    components["dwell_efficiency"] = round(dwell_score, 2)
    
    # Calculate weighted final score
    final_score = (
        completion_score * WEIGHT_COMPLETION_RATE +
        on_time_score * WEIGHT_ON_TIME_PERFORMANCE +
        no_show_score * WEIGHT_NO_SHOW_PENALTY +
        anomaly_score * WEIGHT_ANOMALY_PENALTY +
        dwell_score * WEIGHT_DWELL_EFFICIENCY
    )
    
    # Clamp to 0-100
    final_score = max(0.0, min(100.0, final_score))
    
    # Determine tier
    if final_score >= TIER_A_THRESHOLD:
        tier = "A"
    elif final_score >= TIER_B_THRESHOLD:
        tier = "B"
    elif final_score >= TIER_C_THRESHOLD:
        tier = "C"
    else:
        tier = "D"
    
    # Calculate confidence based on sample size
    if total >= HIGH_CONFIDENCE_BOOKINGS:
        confidence = 1.0
    elif total >= LOW_CONFIDENCE_BOOKINGS:
        confidence = 0.5 + (total - LOW_CONFIDENCE_BOOKINGS) / (HIGH_CONFIDENCE_BOOKINGS - LOW_CONFIDENCE_BOOKINGS) * 0.5
    else:
        confidence = total / LOW_CONFIDENCE_BOOKINGS * 0.5
    
    # Generate human-readable reasons
    reasons = _generate_reasons(
        tier=tier,
        completion_rate=completion_rate,
        no_show_rate=no_show_rate,
        late_rate=late_rate,
        avg_delay=avg_delay,
        anomaly_rate=anomaly_rate,
        total=total
    )
    
    # Stats summary
    stats_summary = {
        "total_bookings": total,
        "completion_rate": round(completion_rate * 100, 1),
        "on_time_rate": round((1.0 - late_rate) * 100, 1),
        "no_show_rate": round(no_show_rate * 100, 1),
        "avg_delay_minutes": round(avg_delay, 1),
        "anomaly_rate": round(anomaly_rate * 100, 1)
    }
    
    return {
        "score": round(final_score, 2),
        "tier": tier,
        "components": components,
        "reasons": reasons,
        "confidence": round(confidence, 2),
        "stats_summary": stats_summary
    }


def _generate_reasons(
    tier: str,
    completion_rate: float,
    no_show_rate: float,
    late_rate: float,
    avg_delay: float,
    anomaly_rate: float,
    total: int
) -> List[str]:
    """Generate 3-6 human-readable reasons for the score."""
    reasons = []
    
    # Tier commentary
    tier_messages = {
        "A": "Excellent overall performance",
        "B": "Good performance with room for improvement",
        "C": "Acceptable performance but needs attention",
        "D": "Performance needs significant improvement"
    }
    reasons.append(tier_messages.get(tier, "Performance assessed"))
    
    # Completion rate
    if completion_rate >= 0.95:
        reasons.append(f"High completion rate ({completion_rate*100:.1f}%)")
    elif completion_rate >= 0.85:
        reasons.append(f"Good completion rate ({completion_rate*100:.1f}%)")
    else:
        reasons.append(f"Low completion rate ({completion_rate*100:.1f}%) - improvement needed")
    
    # No-show issues
    if no_show_rate > MAX_ACCEPTABLE_NO_SHOW_RATE:
        reasons.append(f"High no-show rate ({no_show_rate*100:.1f}%) impacts reliability")
    elif no_show_rate < 0.02:
        reasons.append(f"Excellent reliability with minimal no-shows ({no_show_rate*100:.1f}%)")
    
    # On-time performance
    if late_rate > 0.15:
        reasons.append(f"Punctuality issues: {late_rate*100:.1f}% late arrivals")
    elif late_rate < 0.05 and avg_delay < 5:
        reasons.append(f"Excellent punctuality record")
    
    # Anomalies
    if anomaly_rate > MAX_ACCEPTABLE_ANOMALY_RATE:
        reasons.append(f"High anomaly rate ({anomaly_rate*100:.1f}%) requires investigation")
    
    # Sample size caveat
    if total < LOW_CONFIDENCE_BOOKINGS:
        reasons.append(f"Score based on limited data ({total} bookings) - more history needed for confidence")
    elif total >= HIGH_CONFIDENCE_BOOKINGS:
        reasons.append(f"Score based on substantial history ({total} bookings)")
    
    # Return 3-6 most relevant reasons
    return reasons[:6]
