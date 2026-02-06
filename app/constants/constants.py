"""
Global Constants

Non-business constants used throughout the application.
These are infrastructure/technical constants, not domain thresholds.

Configuration values loaded from environment variables remain in service clients.
These are fallback defaults and standard values only.
"""

import uuid
from typing import Optional

# ============================================================================
# HTTP Headers
# ============================================================================

TRACE_HEADER_NAME = "x-request-id"
USER_ROLE_HEADER_NAME = "x-user-role"
USER_ID_HEADER_NAME = "x-user-id"
CARRIER_ID_HEADER_NAME = "x-carrier-id"


# ============================================================================
# Default Values
# ============================================================================

# Default lookback window for historical queries (in days)
DEFAULT_WINDOW_DAYS = 90

# Maximum batch size for batch operations (safety limit)
MAX_BATCH_REFS = 50

# Maximum bookings per batch status request
MAX_BATCH_BOOKINGS = 100

# Default timezone for datetime operations
DEFAULT_TIMEZONE = "UTC"


# ============================================================================
# Response Metadata
# ============================================================================

# Component names for proofs.component field
COMPONENT_ORCHESTRATOR = "orchestrator"
COMPONENT_AGENT = "agent"
COMPONENT_MODEL = "model"
COMPONENT_SERVICE = "service"
COMPONENT_API = "api"


# ============================================================================
# Helper Functions
# ============================================================================

def normalize_trace_id(trace_id: Optional[str]) -> str:
    """
    Normalize trace ID, generate new one if missing/invalid.
    
    Args:
        trace_id: Trace ID string (may be None or empty)
    
    Returns:
        Valid trace ID string (never None)
    
    Example:
        >>> normalize_trace_id("abc123")
        'abc123'
        >>> normalize_trace_id(None)  # generates new UUID
        'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'
        >>> normalize_trace_id("")  # generates new UUID
        'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'
    """
    if not trace_id or not isinstance(trace_id, str) or not trace_id.strip():
        return str(uuid.uuid4())
    return trace_id.strip()


def short_request_id(trace_id: str) -> str:
    """
    Get short version of trace ID for logging (first 8 chars).
    
    Safe even if trace_id is shorter than 8 characters.
    
    Args:
        trace_id: Full trace ID string
    
    Returns:
        First 8 characters (or full string if shorter)
    
    Example:
        >>> short_request_id("abc12345-6789-0000-1111-222222222222")
        'abc12345'
        >>> short_request_id("abc123")
        'abc123'
    """
    if not trace_id or not isinstance(trace_id, str):
        return "unknown"
    return trace_id[:8] if len(trace_id) >= 8 else trace_id


def validate_batch_size(size: int, max_size: int = MAX_BATCH_REFS) -> bool:
    """
    Validate batch size is within limits.
    
    Args:
        size: Requested batch size
        max_size: Maximum allowed size (default: MAX_BATCH_REFS)
    
    Returns:
        True if valid, False if too large or invalid
    
    Example:
        >>> validate_batch_size(10)
        True
        >>> validate_batch_size(100)
        False
        >>> validate_batch_size(0)
        False
    """
    return 1 <= size <= max_size
