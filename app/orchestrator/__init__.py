"""
Orchestrator Package - Multi-Agent Message Routing

This package provides intelligent message routing with:
- Intent detection (multilingual FR/EN)
- Entity extraction (booking refs, dates, terminals, etc.)
- RBAC policy enforcement
- Standardized response formatting
- Integration with agents and models

Version: 1.0.0
"""

from app.orchestrator.orchestrator import Orchestrator
from app.orchestrator.intent_detector import detect_intent, IntentResult
from app.orchestrator.entity_extractor import extract_entities
from app.orchestrator.policy import check_access, PolicyResult
from app.orchestrator.response_formatter import (
    format_success,
    format_error,
    format_validation_error,
    standardize_response
)

__version__ = "1.0.0"

__all__ = [
    "Orchestrator",
    "detect_intent",
    "IntentResult",
    "extract_entities",
    "check_access",
    "PolicyResult",
    "format_success",
    "format_error",
    "format_validation_error",
    "standardize_response",
]
