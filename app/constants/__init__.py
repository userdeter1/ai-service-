"""
Constants Package

Centralized constants for the AI Service application.

Exports:
- Role constants (ADMIN, OPERATOR, CARRIER, ANON)
- Intent constants (BOOKING_STATUS, CARRIER_SCORE, etc.)
- Threshold values (carrier tiers, slot availability, risk levels)
- Global constants (headers, defaults, component names)

Safe to import anywhere - no heavy dependencies or circular imports.
"""

# Role constants
from .roles import (
    ADMIN,
    OPERATOR,
    CARRIER,
    ANON,
    ALL_ROLES,
    DEFAULT_ROLE,
    is_valid_role,
    normalize_role,
)

# Intent constants
from .intents import (
    # Core intents
    BOOKING_STATUS,
    CARRIER_SCORE,
    SLOT_AVAILABILITY,
    SLOT_RECOMMENDATION,
    DRIVER_NOSHOW_RISK,
    PASSAGE_HISTORY,
    TRAFFIC_FORECAST,
    ANOMALY_DETECTION,
    BLOCKCHAIN_AUDIT,
    # Meta intents
    HELP,
    HEALTH_CHECK,
    SMALLTALK,
    UNKNOWN,
    # Collections
    ALL_INTENTS,
    DEFAULT_INTENT,
    # Routing maps
    INTENT_TO_AGENT,
    INTENT_TO_MODEL,
    # Helpers
    is_valid_intent,
    normalize_intent,
    get_agent_for_intent,
    get_model_for_intent,
)

# Threshold constants
from .thresholds import (
    # Carrier thresholds
    TIER_A_THRESHOLD,
    TIER_B_THRESHOLD,
    TIER_C_THRESHOLD,
    LOW_CARRIER_SCORE_THRESHOLD,
    # Slot thresholds
    MIN_REMAINING_CAPACITY,
    LOW_AVAILABILITY_RATIO,
    EARLY_BUFFER_MINUTES,
    # Risk thresholds
    RISK_LOW_MAX,
    RISK_MEDIUM_MAX,
    # Helpers
    carrier_tier,
    risk_level,
    is_low_carrier_score,
    is_low_availability,
)

# Global constants
from .constants import (
    # Headers
    TRACE_HEADER_NAME,
    USER_ROLE_HEADER_NAME,
    USER_ID_HEADER_NAME,
    CARRIER_ID_HEADER_NAME,
    # Defaults
    DEFAULT_WINDOW_DAYS,
    MAX_BATCH_REFS,
    MAX_BATCH_BOOKINGS,
    DEFAULT_TIMEZONE,
    # Components
    COMPONENT_ORCHESTRATOR,
    COMPONENT_AGENT,
    COMPONENT_MODEL,
    COMPONENT_SERVICE,
    COMPONENT_API,
    # Helpers
    normalize_trace_id,
    short_request_id,
    validate_batch_size,
)

__all__ = [
    # Roles
    "ADMIN",
    "OPERATOR",
    "CARRIER",
    "ANON",
    "ALL_ROLES",
    "DEFAULT_ROLE",
    "is_valid_role",
    "normalize_role",
    # Intents
    "BOOKING_STATUS",
    "CARRIER_SCORE",
    "SLOT_AVAILABILITY",
    "SLOT_RECOMMENDATION",
    "DRIVER_NOSHOW_RISK",
    "PASSAGE_HISTORY",
    "TRAFFIC_FORECAST",
    "ANOMALY_DETECTION",
    "BLOCKCHAIN_AUDIT",
    "HELP",
    "HEALTH_CHECK",
    "SMALLTALK",
    "UNKNOWN",
    "ALL_INTENTS",
    "DEFAULT_INTENT",
    "INTENT_TO_AGENT",
    "INTENT_TO_MODEL",
    "is_valid_intent",
    "normalize_intent",
    "get_agent_for_intent",
    "get_model_for_intent",
    # Thresholds
    "TIER_A_THRESHOLD",
    "TIER_B_THRESHOLD",
    "TIER_C_THRESHOLD",
    "LOW_CARRIER_SCORE_THRESHOLD",
    "MIN_REMAINING_CAPACITY",
    "LOW_AVAILABILITY_RATIO",
    "EARLY_BUFFER_MINUTES",
    "RISK_LOW_MAX",
    "RISK_MEDIUM_MAX",
    "carrier_tier",
    "risk_level",
    "is_low_carrier_score",
    "is_low_availability",
    # Global
    "TRACE_HEADER_NAME",
    "USER_ROLE_HEADER_NAME",
    "USER_ID_HEADER_NAME",
    "CARRIER_ID_HEADER_NAME",
    "DEFAULT_WINDOW_DAYS",
    "MAX_BATCH_REFS",
    "MAX_BATCH_BOOKINGS",
    "DEFAULT_TIMEZONE",
    "COMPONENT_ORCHESTRATOR",
    "COMPONENT_AGENT",
    "COMPONENT_MODEL",
    "COMPONENT_SERVICE",
    "COMPONENT_API",
    "normalize_trace_id",
    "short_request_id",
    "validate_batch_size",
]
