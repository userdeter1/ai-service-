"""
Slot Recommendation Algorithm

Deterministic algorithm for recommending optimal time slots based on availability,
carrier performance, and time preferences.

No external ML or randomness - purely based on rules and scoring.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# Scoring weights
WEIGHT_AVAILABILITY = 0.40  # Prefer slots with more remaining capacity
WEIGHT_TIME_DISTANCE = 0.30  # Prefer slots closer to requested time
WEIGHT_CARRIER_BUFFER = 0.20  # Low-score carriers get buffer recommendation
WEIGHT_GATE_PREFERENCE = 0.10  # Prefer certain gates if specified

# Thresholds
MIN_REMAINING_CAPACITY = 1  # Must have at least 1 spot
LOW_CARRIER_SCORE_THRESHOLD = 60  # Carriers below this need more buffer
EARLY_BUFFER_MINUTES = 60  # Suggest slots 60min earlier for low-score carriers


# ============================================================================
# Recommendation Functions
# ============================================================================


def recommend_slots(
    requested: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    carrier_score: Optional[float] = None,
    traffic_forecast: Optional[Dict[str, Any]] = None,
    preferences: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Recommend best slots from candidates.
    
    Args:
        requested: Requested slot info (start, terminal).
        candidates: List of available slots.
        carrier_score: Optional carrier reliability score.
        traffic_forecast: Optional traffic data.
        preferences: Optional user preferences.
    
    Returns:
        Dict with recommended, ranked, strategy, reasons.
    """
    if not candidates:
        return {
            "recommended": [],
            "ranked": [],
            "strategy": "no_candidates",
            "reasons": ["No available slots match your criteria"]
        }
    
    # Parse requested time
    requested_time = _parse_time(requested.get("start"))
    requested_gate = requested.get("gate")
    
    # Filter: only slots with remaining capacity
    available = [s for s in candidates if s.get("remaining", 0) >= MIN_REMAINING_CAPACITY]
    
    if not available:
        return {
            "recommended": [],
            "ranked": [],
            "strategy": "no_capacity",
            "reasons": ["All slots are fully booked"]
        }
    
    # Determine strategy based on carrier score
    if carrier_score is not None and carrier_score < LOW_CARRIER_SCORE_THRESHOLD:
        strategy = "buffer_recommended"
        prefer_earlier = True
    else:
        strategy = "standard"
        prefer_earlier = False
    
    # Score each slot
    scored_slots = []
    for slot in available:
        rank_score, reasons = _score_slot(
            slot=slot,
            requested_time=requested_time,
            requested_gate=requested_gate,
            carrier_score=carrier_score,
            prefer_earlier=prefer_earlier,
            preferences=preferences
        )
        
        scored_slots.append({
            **slot,
            "rank_score": round(rank_score, 2),
            "rank_reasons": reasons
        })
    
    # Sort by rank score (descending)
    scored_slots.sort(key=lambda x: x["rank_score"], reverse=True)
    
    # Top 3-5 recommendations
    recommended = scored_slots[:5]
    
    # Generate overall reasons
    overall_reasons = _generate_overall_reasons(
        strategy=strategy,
        carrier_score=carrier_score,
        recommended=recommended
    )
    
    return {
        "recommended": recommended,
        "ranked": scored_slots,
        "strategy": strategy,
        "reasons": overall_reasons
    }


def _score_slot(
    slot: Dict[str, Any],
    requested_time: Optional[datetime],
    requested_gate: Optional[str],
    carrier_score: Optional[float],
    prefer_earlier: bool,
    preferences: Optional[Dict[str, Any]]
) -> Tuple[float, List[str]]:
    """
    Score a single slot (0-100).
    
    Returns: (score, reasons)
    """
    score = 0.0
    reasons = []
    
    # 1. Availability score (40%)
    remaining = slot.get("remaining", 0)
    capacity = slot.get("capacity", 1)
    availability_ratio = remaining / capacity if capacity > 0 else 0
    availability_score = availability_ratio * 100
    score += availability_score * WEIGHT_AVAILABILITY
    
    if remaining > capacity * 0.5:
        reasons.append(f"High availability ({remaining}/{capacity} spots)")
    elif remaining > capacity * 0.2:
        reasons.append(f"Moderate availability ({remaining}/{capacity} spots)")
    else:
        reasons.append(f"Limited availability ({remaining}/{capacity} spots)")
    
    # 2. Time distance score (30%)
    slot_time = _parse_time(slot.get("start"))
    if requested_time and slot_time:
        # Compute absolute time difference in minutes
        time_diff_minutes = abs((slot_time - requested_time).total_seconds() / 60)
        
        # Base time score - closer is better
        if time_diff_minutes == 0:
            time_score = 100
            reasons.append("Exact time match")
        else:
            # Start with base score that decreases with distance
            base_time_score = max(0, 100 - time_diff_minutes / 3)
            
            # Apply preference logic
            if prefer_earlier and slot_time > requested_time:
                # Penalize later slots for low-score carriers, but don't go negative
                penalty_factor = 0.5  # 50% penalty for later slots
                time_score = max(0, base_time_score * penalty_factor)
                if time_diff_minutes > EARLY_BUFFER_MINUTES:
                    reasons.append(f"Later than requested (+{int(time_diff_minutes)}min) - consider earlier")
                else:
                    reasons.append(f"Later by {int(time_diff_minutes)}min")
            elif slot_time < requested_time:
                # Earlier slots - good for buffer
                time_score = base_time_score
                if time_diff_minutes <= EARLY_BUFFER_MINUTES:
                    reasons.append(f"Earlier by {int(time_diff_minutes)}min - good buffer")
                else:
                    reasons.append(f"Earlier by {int(time_diff_minutes)}min")
            else:
                # Same time or later (normal case)
                time_score = base_time_score
                if time_diff_minutes <= 30:
                    reasons.append(f"Close to requested time (+/-{int(time_diff_minutes)}min)")
                else:
                    reasons.append(f"Time difference: {int(time_diff_minutes)}min")
        
        # Clamp time_score to 0-100
        time_score = max(0, min(100, time_score))
        score += time_score * WEIGHT_TIME_DISTANCE
    else:
        # No time info, neutral score
        score += 50 * WEIGHT_TIME_DISTANCE
    
    # 3. Carrier buffer score (20%)
    if carrier_score is not None and carrier_score < LOW_CARRIER_SCORE_THRESHOLD:
        # Low-score carriers: prefer slots with more buffer
        if slot_time and requested_time and slot_time < requested_time:
            buffer_score = 100  # Earlier is ideal
            reasons.append("Early slot recommended for reliability buffer")
        elif remaining > capacity * 0.5:
            buffer_score = 80  # High capacity as fallback
        else:
            buffer_score = 50
        
        score += buffer_score * WEIGHT_CARRIER_BUFFER
    else:
        # Normal carriers: neutral
        score += 70 * WEIGHT_CARRIER_BUFFER
    
    # 4. Gate preference score (10%)
    if requested_gate and slot.get("gate") == requested_gate:
        gate_score = 100
        reasons.append(f"Matches requested gate {requested_gate}")
    else:
        gate_score = 50  # Neutral if no preference or different gate
    
    score += gate_score * WEIGHT_GATE_PREFERENCE
    
    # Final clamp to 0-100
    score = max(0.0, min(100.0, score))
    
    return score, reasons


def _parse_time(time_input: Any) -> Optional[datetime]:
    """Parse time from various formats."""
    if isinstance(time_input, datetime):
        return time_input
    
    if isinstance(time_input, str):
        try:
            # Try ISO format
            return datetime.fromisoformat(time_input.replace("Z", "+00:00"))
        except Exception:
            try:
                # Try common formats
                for fmt in ["%Y-%m-%d %H:%M:%S", "%H:%M", "%Y-%m-%dT%H:%M:%S"]:
                    return datetime.strptime(time_input, fmt)
            except Exception:
                pass
    
    return None


def _generate_overall_reasons(
    strategy: str,
    carrier_score: Optional[float],
    recommended: List[Dict[str, Any]]
) -> List[str]:
    """Generate overall reasons for recommendations."""
    reasons = []
    
    if strategy == "buffer_recommended":
        reasons.append(
            f"Carrier score is {carrier_score:.0f}/100 - recommending earlier slots for reliability buffer"
        )
    
    if recommended:
        top_slot = recommended[0]
        reasons.append(
            f"Top recommendation: {top_slot.get('start')} at {top_slot.get('terminal')}/{top_slot.get('gate')} "
            f"({top_slot.get('remaining')}/{top_slot.get('capacity')} available)"
        )
    
    if len(recommended) > 1:
        reasons.append(f"Showing top {len(recommended)} alternatives")
    
    return reasons if reasons else ["Slots ranked by availability and time preference"]
