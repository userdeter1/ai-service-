"""
Booking Service HTTP Client

Provides async interface to the Booking Service backend for booking status queries.
Uses a module-level singleton AsyncClient for efficient connection pooling.

Functions:
- get_booking_status: Get status for a single booking reference
- get_bookings_batch: Get status for multiple booking references
- aclose_client: Close the HTTP client (call during app shutdown)

All functions forward Authorization headers and handle common HTTP errors.
"""

import os
import logging
from typing import Optional, Dict, Any, List
import httpx
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration - Read from environment
# ============================================================================

BOOKING_SERVICE_URL = os.getenv("BOOKING_SERVICE_URL", "http://localhost:3002")

# Endpoint paths (configurable via env)
BOOKING_STATUS_PATH = os.getenv("BOOKING_STATUS_PATH", "/bookings/{booking_ref}")
BOOKING_BATCH_STATUS_PATH = os.getenv("BOOKING_BATCH_STATUS_PATH", "/bookings/batch")

# HTTP client timeout (seconds)
REQUEST_TIMEOUT = float(os.getenv("BOOKING_CLIENT_TIMEOUT", "15.0"))

# Connection pool limits for scalability
MAX_CONNECTIONS = int(os.getenv("BOOKING_CLIENT_MAX_CONNECTIONS", "100"))
MAX_KEEPALIVE_CONNECTIONS = int(os.getenv("BOOKING_CLIENT_MAX_KEEPALIVE", "20"))

# Security: Include raw payload in response (default: False to prevent huge payloads)
INCLUDE_RAW_PAYLOAD = os.getenv("BOOKING_INCLUDE_RAW", "false").lower() in ("true", "1", "yes")

logger.info(f"Booking Service client configured with URL: {BOOKING_SERVICE_URL}")


# ============================================================================
# Module-level HTTP Client (Singleton with Connection Pooling)
# ============================================================================

_client: Optional[httpx.AsyncClient] = None


def get_client() -> httpx.AsyncClient:
    """
    Get or create the module-level httpx.AsyncClient singleton.
    Initializes client with connection pooling on first call.
    
    Returns:
        Shared httpx.AsyncClient instance
    """
    global _client
    
    # Create client if it doesn't exist or is closed
    if _client is None or _client.is_closed:
        limits = httpx.Limits(
            max_connections=MAX_CONNECTIONS,
            max_keepalive_connections=MAX_KEEPALIVE_CONNECTIONS
        )
        
        _client = httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            limits=limits,
            follow_redirects=False  # Explicit redirect handling
        )
        logger.info("Initialized Booking Service httpx.AsyncClient with connection pooling")
    
    return _client


async def aclose_client() -> None:
    """
    Close the module-level httpx.AsyncClient gracefully.
    Should be called during FastAPI shutdown (lifespan).
    
    NOTE: To properly close this client during app shutdown, add to your
    FastAPI lifespan or shutdown event handler:
    
    from app.tools import booking_service_client
    
    @app.on_event("shutdown")
    async def shutdown_event():
        await booking_service_client.aclose_client()
    """
    global _client
    
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        logger.info("Closed Booking Service httpx.AsyncClient")
        _client = None


# ============================================================================
# Helper Functions
# ============================================================================


def _build_headers(
    auth_header: Optional[str] = None,
    request_id: Optional[str] = None
) -> Dict[str, str]:
    """
    Build request headers with optional Authorization and x-request-id.
    
    Args:
        auth_header: Optional Authorization header value
        request_id: Optional request ID for tracing
    
    Returns:
        Headers dictionary
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    if auth_header:
        headers["Authorization"] = auth_header
    
    if request_id:
        headers["x-request-id"] = request_id
    
    return headers


def _handle_http_error(e: httpx.HTTPStatusError) -> None:
    """
    Map httpx HTTP errors to FastAPI HTTPException with appropriate status codes.
    
    Security: Logs full backend error message server-side but exposes only
    safe, generic messages to prevent information leakage.
    
    Raises:
        HTTPException with appropriate status code and safe message
    """
    status_code = e.response.status_code
    
    # Try to extract error message from response (for logging only)
    try:
        error_data = e.response.json()
        error_message = error_data.get("message") or error_data.get("detail") or str(error_data)
    except Exception:
        error_message = e.response.text or f"Status {status_code}"
    
    # Log full error message server-side for debugging
    logger.warning(f"Booking service error {status_code}: {error_message}")
    
    # Map status codes to SAFE user-facing messages (don't leak backend internals)
    if status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    elif status_code == 403:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden"
        )
    elif status_code == 404:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    elif status_code == 422:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid request"
        )
    elif status_code >= 500:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Booking service unavailable"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Booking service error"
        )


def _handle_connection_error(e: Exception) -> None:
    """
    Handle connection errors (timeout, network issues, etc.).
    
    Raises:
        HTTPException with 503 status
    """
    logger.error(f"Booking service connection error: {type(e).__name__}: {e}")
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Cannot connect to booking service: {type(e).__name__}"
    )


def _normalize_booking(data: Any) -> Dict[str, Any]:
    """
    Normalize booking response to consistent format.
    Handles different response shapes and field names.
    
    Args:
        data: Raw booking data from backend
    
    Returns:
        Normalized booking dict with standard field names:
        {
            "booking_ref": str,
            "status": str,
            "terminal": str,
            "gate": str,
            "slot_time": str,
            "last_update": str,
            "raw": dict (optional)
        }
    """
    if not isinstance(data, dict):
        return {"booking_ref": str(data), "status": "unknown"}
    
    # Extract nested data if present
    booking = data.get("data", data)
    
    # Normalize field names (try multiple possible field names)
    booking_ref = (
        booking.get("booking_ref") or
        booking.get("bookingRef") or
        booking.get("ref") or
        booking.get("reference") or
        "unknown"
    )
    
    status_value = (
        booking.get("status") or
        booking.get("bookingStatus") or
        "unknown"
    )
    
    terminal = (
        booking.get("terminal") or
        booking.get("terminalId") or
        booking.get("terminal_id") or
        "N/A"
    )
    
    gate = (
        booking.get("gate") or
        booking.get("gateId") or
        booking.get("gate_id") or
        "N/A"
    )
    
    slot_time = (
        booking.get("slot_time") or
        booking.get("slotTime") or
        booking.get("timeWindow") or
        booking.get("time_window") or
        "N/A"
    )
    
    last_update = (
        booking.get("last_update") or
        booking.get("lastUpdate") or
        booking.get("updatedAt") or
        booking.get("updated_at") or
        "N/A"
    )
    
    normalized = {
        "booking_ref": str(booking_ref),
        "status": str(status_value),
        "terminal": str(terminal),
        "gate": str(gate),
        "slot_time": str(slot_time),
        "last_update": str(last_update)
    }
    
    # Only include raw payload if explicitly enabled (prevents huge responses)
    if INCLUDE_RAW_PAYLOAD:
        normalized["raw"] = booking
    
    return normalized


# ============================================================================
# Public API Functions
# ============================================================================


async def get_booking_status(
    booking_ref: str,
    auth_header: Optional[str] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get status for a single booking reference.
    
    Args:
        booking_ref: Booking reference number (e.g., "REF12345")
        auth_header: Optional Authorization header to forward
        request_id: Optional request ID for tracing
    
    Returns:
        Normalized booking dict with fields:
        - booking_ref: str
        - status: str
        - terminal: str
        - gate: str
        - slot_time: str
        - last_update: str
        - raw: dict (original response)
    
    Raises:
        HTTPException: On backend errors (401, 403, 404, 503, etc.)
    """
    url = f"{BOOKING_SERVICE_URL}{BOOKING_STATUS_PATH}".format(booking_ref=booking_ref)
    headers = _build_headers(auth_header, request_id)
    
    logger.debug(f"Fetching booking status for {booking_ref}")
    
    try:
        client = get_client()
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        normalized = _normalize_booking(data)
        logger.info(f"Retrieved booking status for {booking_ref}: {normalized['status']}")
        return normalized
    except httpx.HTTPStatusError as e:
        _handle_http_error(e)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
        _handle_connection_error(e)
    except Exception as e:
        logger.exception(f"Unexpected error fetching booking status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {type(e).__name__}"
        )


async def get_bookings_batch(
    booking_refs: List[str],
    auth_header: Optional[str] = None,
    request_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get status for multiple booking references in one request.
    
    Args:
        booking_refs: List of booking reference numbers
        auth_header: Optional Authorization header to forward
        request_id: Optional request ID for tracing
    
    Returns:
        List of normalized booking dicts (same format as get_booking_status)
    
    Raises:
        HTTPException: On backend errors (401, 403, 503, etc.)
    """
    url = f"{BOOKING_SERVICE_URL}{BOOKING_BATCH_STATUS_PATH}"
    headers = _build_headers(auth_header, request_id)
    payload = {"refs": booking_refs}
    
    logger.debug(f"Fetching batch booking status for {len(booking_refs)} refs")
    
    try:
        client = get_client()
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Handle different response shapes
        if isinstance(data, dict):
            # Response might be {"data": [...]} or {"bookings": [...]}
            bookings_list = data.get("data") or data.get("bookings") or []
        elif isinstance(data, list):
            bookings_list = data
        else:
            bookings_list = []
        
        # Normalize each booking
        normalized = [_normalize_booking(booking) for booking in bookings_list]
        logger.info(f"Retrieved {len(normalized)} booking statuses")
        return normalized
    except httpx.HTTPStatusError as e:
        _handle_http_error(e)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
        _handle_connection_error(e)
    except Exception as e:
        logger.exception(f"Unexpected error fetching batch booking status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {type(e).__name__}"
        )
