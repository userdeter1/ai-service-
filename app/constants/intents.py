"""
Intent Constants

Defines all intent strings used by orchestrator/intent_detector and routed to
appropriate agents/models/handlers.

Intent names are STABLE identifiers - do not change without coordinating
with orchestrator, agents, and API routers.

Usage:
- Orchestrator: Uses INTENT_TO_AGENT and INTENT_TO_MODEL for routing
- Intent detector: Returns normalized intent from ALL_INTENTS
- Agents: Registered under agent names from INTENT_TO_AGENT values
- Models: Registered under model names from INTENT_TO_MODEL values
"""

from typing import Optional

# ============================================================================
# Intent Constants (STABLE - do not rename without coordination)
# ============================================================================

# Core operational intents
BOOKING_STATUS = "booking_status"
CARRIER_SCORE = "carrier_score"
SLOT_AVAILABILITY = "slot_availability"
SLOT_RECOMMENDATION = "slot_recommendation"
DRIVER_NOSHOW_RISK = "driver_noshow_risk"
PASSAGE_HISTORY = "passage_history"
TRAFFIC_FORECAST = "traffic_forecast"
ANOMALY_DETECTION = "anomaly_detection"
BLOCKCHAIN_AUDIT = "blockchain_audit"

# Analytics intents
ANALYTICS_STRESS = "analytics_stress_index"
ANALYTICS_ALERTS = "analytics_alerts"
ANALYTICS_WHAT_IF = "analytics_what_if"

# Meta intents
HELP = "help"
HEALTH_CHECK = "health_check"
SMALLTALK = "smalltalk"
UNKNOWN = "unknown"

# All valid intents
ALL_INTENTS = {
    BOOKING_STATUS,
    CARRIER_SCORE,
    SLOT_AVAILABILITY,
    SLOT_RECOMMENDATION,
    DRIVER_NOSHOW_RISK,
    PASSAGE_HISTORY,
    TRAFFIC_FORECAST,
    ANOMALY_DETECTION,
    BLOCKCHAIN_AUDIT,
    ANALYTICS_STRESS,
    ANALYTICS_ALERTS,
    ANALYTICS_WHAT_IF,
    HELP,
    HEALTH_CHECK,
    SMALLTALK,
    UNKNOWN,
}

# Default intent for unrecognized/missing input
DEFAULT_INTENT = UNKNOWN


# ============================================================================
# Intent Routing Maps
# ============================================================================

# Map intent to agent class name or registry key
# Orchestrator uses this to instantiate the correct agent
INTENT_TO_AGENT = {
    BOOKING_STATUS: "BookingAgent",
    CARRIER_SCORE: "CarrierScoreAgent",
    SLOT_AVAILABILITY: "SlotAgent",
    SLOT_RECOMMENDATION: "SlotAgent",
    DRIVER_NOSHOW_RISK: "DriverNoshowAgent",
    PASSAGE_HISTORY: "PassageAgent",
    TRAFFIC_FORECAST: "TrafficAgent",
    ANOMALY_DETECTION: "AnomalyAgent",
    BLOCKCHAIN_AUDIT: "BlockchainAgent",
    ANALYTICS_STRESS: "AnalyticsAgent",
    ANALYTICS_ALERTS: "AnalyticsAgent",
    ANALYTICS_WHAT_IF: "AnalyticsAgent",
    # Meta intents handled by orchestrator directly (no agent)
    HELP: None,
    HEALTH_CHECK: None,
    SMALLTALK: None,
    UNKNOWN: None,
}

# Map intent to model registry name
# Used when agent delegates to model for predictions
# IMPORTANT: These strings MUST match model registry keys in app.models.loader
INTENT_TO_MODEL = {
    CARRIER_SCORE: "carrier_scoring",              # SYNC: model registry key
    SLOT_RECOMMENDATION: "slot_recommendation",    # SYNC: model registry key
    DRIVER_NOSHOW_RISK: "driver_noshow_risk",      # SYNC: model registry key
    TRAFFIC_FORECAST: "traffic_model",             # SYNC: model registry key (if exists)
    ANOMALY_DETECTION: "anomaly_model",            # SYNC: model registry key (if exists)
}


# ============================================================================
# Helper Functions
# ============================================================================

def is_valid_intent(intent: str) -> bool:
    """
    Check if intent is valid.
    
    Args:
        intent: Intent string to validate
    
    Returns:
        True if valid intent, False otherwise
    
    Example:
        >>> is_valid_intent("booking_status")
        True
        >>> is_valid_intent("invalid_intent")
        False
    """
    if not intent or not isinstance(intent, str):
        return False
    return intent.strip().lower() in ALL_INTENTS


def normalize_intent(intent: Optional[str]) -> str:
    """
    Normalize intent string to lowercase, return DEFAULT_INTENT if invalid.
    
    Args:
        intent: Intent string (may be None, mixed case, or invalid)
    
    Returns:
        Normalized lowercase intent string, or DEFAULT_INTENT if invalid
    
    Example:
        >>> normalize_intent("BOOKING_STATUS")
        'booking_status'
        >>> normalize_intent("Slot_Availability")
        'slot_availability'
        >>> normalize_intent(None)
        'unknown'
        >>> normalize_intent("invalid")
        'unknown'
    """
    if not intent or not isinstance(intent, str):
        return DEFAULT_INTENT
    
    normalized = intent.strip().lower()
    
    if normalized in ALL_INTENTS:
        return normalized
    
    return DEFAULT_INTENT


def get_agent_for_intent(intent: str) -> Optional[str]:
    """
    Get agent class name for intent.
    
    Args:
        intent: Intent string (should be normalized)
    
    Returns:
        Agent class name or None if no agent handles this intent
    
    Example:
        >>> get_agent_for_intent("booking_status")
        'BookingAgent'
        >>> get_agent_for_intent("help")
        None
    """
    return INTENT_TO_AGENT.get(intent)


def get_model_for_intent(intent: str) -> Optional[str]:
    """
    Get model registry name for intent.
    
    Args:
        intent: Intent string (should be normalized)
    
    Returns:
        Model registry key or None if no model needed
    
    Example:
        >>> get_model_for_intent("carrier_score")
        'carrier_scoring'
        >>> get_model_for_intent("booking_status")
        None
    """
    return INTENT_TO_MODEL.get(intent)
