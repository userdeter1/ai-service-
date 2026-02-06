"""
Response Formatter - Standardized Response Formatting

Provides consistent response structure across all components.
Ensures security by sanitizing error messages.

Standard response format:
{
    "message": str,        # Human-readable message
    "data": dict,          # Structured data
    "proofs": dict         # Tracing and metadata
}

All responses include:
- Safe error messages (no backend internals)
- Trace IDs for debugging
- Timestamps
- Component identification
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================================
# Response Format Functions
# ============================================================================

def format_success(
    message: str,
    data: Optional[Dict[str, Any]] = None,
    proofs: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format successful response.
    
    Args:
        message: Human-readable success message
        data: Structured result data
        proofs: Tracing and metadata
        trace_id: Request trace ID
    
    Returns:
        Standardized response dict
    """
    response = {
        "message": message,
        "data": data or {},
        "proofs": _build_proofs(proofs, trace_id, status="ok")
    }
    
    return response


def format_error(
    message: str,
    error_type: str = "Error",
    trace_id: Optional[str] = None,
    status_code: Optional[int] = None,
    data_extra: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Format error response with safe messaging.
    
    Args:
        message: Safe, user-facing error message (NEVER include backend details)
        error_type: Error classification (ModelError, ServiceError, etc.)
        trace_id: Request trace ID
        status_code: HTTP status code
        data_extra: Additional safe data to include
    
    Returns:
        Standardized error response
    """
    response = {
        "message": message,
        "data": {
            "error": error_type,
            **(data_extra or {})
        },
        "proofs": _build_proofs(None, trace_id, status="failed")
    }
    
    if status_code:
        response["data"]["status_code"] = status_code
    
    return response


def format_validation_error(
    message: str,
    missing_field: str,
    example: str,
    suggestion: str,
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format validation error with helpful guidance.
    
    Args:
        message: User-facing validation error message
        missing_field: Which field is missing/invalid
        example: Example value
        suggestion: Helpful suggestion
        trace_id: Request trace ID
    
    Returns:
        Standardized validation error response
    """
    response = {
        "message": message,
        "data": {
            "error": "ValidationError",
            "missing_field": missing_field,
            "example": example,
            "suggestion": suggestion
        },
        "proofs": _build_proofs(None, trace_id, status="validation_failed")
    }
    
    return response


def standardize_response(
    response: Any,
    trace_id: Optional[str] = None,
    component: str = "orchestrator"
) -> Dict[str, Any]:
    """
    Standardize any response to common format.
    
    Handles various response formats:
    - Already standardized: {"message", "data", "proofs"}
    - Model format: {"ok", "result", "error", "proofs"}
    - Agent format: {"message", "data", "proofs"}
    - Raw dict or string
    
    Args:
        response: Response from agent/model/service
        trace_id: Request trace ID
        component: Component name for proofs
    
    Returns:
        Standardized response
    """
    # If already standardized
    if isinstance(response, dict) and "message" in response and "data" in response:
        # Enhance proofs
        if "proofs" not in response:
            response["proofs"] = {}
        response["proofs"] = _build_proofs(response["proofs"], trace_id, component=component)
        return response
    
    # Model format: {"ok": bool, "result": {}, "error": {}, "proofs": {}}
    if isinstance(response, dict) and "ok" in response:
        if response["ok"]:
            # Success
            result = response.get("result", {})
            message = _extract_message_from_data(result) or "Operation completed successfully"
            
            return {
                "message": message,
                "data": result,
                "proofs": _build_proofs(response.get("proofs"), trace_id, status="ok", component=component)
            }
        else:
            # Error
            error = response.get("error", {})
            message = error.get("message", "An error occurred")
            error_type = error.get("type", "ModelError")
            
            return {
                "message": message,
                "data": {
                    "error": error_type,
                    **{k: v for k, v in error.items() if k not in ("message", "type")}
                },
                "proofs": _build_proofs(response.get("proofs"), trace_id, status="failed", component=component)
            }
    
    # Dict with message but no data
    if isinstance(response, dict) and "message" in response:
        return {
            "message": response["message"],
            "data": {k: v for k, v in response.items() if k != "message"},
            "proofs": _build_proofs(response.get("proofs"), trace_id, component=component)
        }
    
    # Raw dict
    if isinstance(response, dict):
        message = response.get("message") or "Operation completed"
        return {
            "message": message,
            "data": response,
            "proofs": _build_proofs(None, trace_id, component=component)
        }
    
    # String
    if isinstance(response, str):
        return {
            "message": response,
            "data": {},
            "proofs": _build_proofs(None, trace_id, component=component)
        }
    
    # Fallback
    return {
        "message": str(response),
        "data": {},
        "proofs": _build_proofs(None, trace_id, component=component)
    }


def _build_proofs(
    proofs: Optional[Dict[str, Any]],
    trace_id: Optional[str],
    status: str = "ok",
    component: str = "orchestrator"
) -> Dict[str, Any]:
    """
    Build/enhance proofs dict with standard fields.
    
    Args:
        proofs: Existing proofs dict (optional)
        trace_id: Request trace ID
        status: Status indicator (ok, failed, etc.)
        component: Component name
    
    Returns:
        Enhanced proofs dict
    """
    base_proofs = proofs.copy() if proofs else {}
    
    # Always include trace_id
    if trace_id and "trace_id" not in base_proofs:
        base_proofs["trace_id"] = trace_id
    
    # Always include timestamp
    if "timestamp" not in base_proofs:
        base_proofs["timestamp"] = datetime.utcnow().isoformat() + "Z"
    
    # Always include status
    if "status" not in base_proofs:
        base_proofs["status"] = status
    
    # Always include component
    if "component" not in base_proofs:
        base_proofs["component"] = component
    
    return base_proofs


def _extract_message_from_data(data: Dict[str, Any]) -> Optional[str]:
    """
    Extract human-readable message from result data.
    
    Tries common patterns like summary fields.
    """
    # Check for common message fields
    for field in ("message", "summary", "description", "explanation"):
        if field in data and isinstance(data[field], str):
            return data[field]
    
    # Build message from key fields
    if "score" in data and "tier" in data:
        return f"Score: {data['score']:.1f}/100 (Tier {data['tier']})"
    
    if "recommended" in data and isinstance(data["recommended"], list):
        count = len(data["recommended"])
        return f"Found {count} recommended slot{'s' if count != 1 else ''}"
    
    if "risk_score" in data:
        return f"Risk score: {data['risk_score']:.2f}"
    
    return None


def sanitize_error_message(message: str) -> str:
    """
    Sanitize error message to remove sensitive information.
    
    Args:
        message: Raw error message
    
    Returns:
        Safe error message
    """
    # Remove URLs
    message = re.sub(r"https?://[^\s]+", "[URL]", message)
    
    # Remove IP addresses
    message = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[IP]", message)
    
    # Remove file paths
    message = re.sub(r"(?:[A-Za-z]:\\|/)[^\s]+", "[PATH]", message)
    
    # Remove SQL-like statements
    message = re.sub(r"\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE)\b.*", "[SQL]", message, flags=re.IGNORECASE)
    
    return message


# Import for sanitize_error_message
import re


# ============================================================================
# Convenience Aliases
# ============================================================================

success = format_success
error = format_error
validation_error = format_validation_error
