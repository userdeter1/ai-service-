"""
Carrier Service HTTP Client

Provides async interface to the Carrier Service backend for carrier profiles and statistics.
Uses a module-level singleton AsyncClient for efficient connection pooling.

Functions:
- get_carrier_profile: Get carrier profile information
- get_carrier_stats: Get carrier performance statistics
- is_endpoint_missing: Check if an HTTPException indicates missing endpoint
- aclose_client: Close the HTTP client (call during app shutdown)

All functions forward Authorization headers and handle common HTTP errors.
"""

import os
import logging
from typing import Optional, Dict, Any
import httpx
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration - Read from environment
# ============================================================================

CARRIER_SERVICE_URL = os.getenv("CARRIER_SERVICE_URL", "http://localhost:3004")

# Endpoint paths (configurable via env)
CARRIER_PROFILE_PATH = os.getenv("CARRIER_PROFILE_PATH", "/carriers/{carrier_id}")
CARRIER_STATS_PATH = os.getenv("CARRIER_STATS_PATH", "/carriers/{carrier_id}/stats")

# HTTP client timeout (seconds)
REQUEST_TIMEOUT = float(os.getenv("CARRIER_CLIENT_TIMEOUT", "15.0"))

# Connection pool limits
MAX_CONNECTIONS = int(os.getenv("CARRIER_CLIENT_MAX_CONNECTIONS", "100"))
MAX_KEEPALIVE_CONNECTIONS = int(os.getenv("CARRIER_CLIENT_MAX_KEEPALIVE", "20"))

logger.info(f"Carrier Service client configured with URL: {CARRIER_SERVICE_URL}")


# ============================================================================
# Module-level HTTP Client (Singleton with Connection Pooling)
# ============================================================================

_client: Optional[httpx.AsyncClient] = None


def get_client() -> httpx.AsyncClient:
    """Get or create the module-level httpx.AsyncClient singleton."""
    global _client
    
    if _client is None or _client.is_closed:
        limits = httpx.Limits(
            max_connections=MAX_CONNECTIONS,
            max_keepalive_connections=MAX_KEEPALIVE_CONNECTIONS
        )
        
        _client = httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            limits=limits,
            follow_redirects=False
        )
        logger.info("Initialized Carrier Service httpx.AsyncClient")
    
    return _client


async def aclose_client() -> None:
    """Close the module-level httpx.AsyncClient gracefully."""
    global _client
    
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        logger.info("Closed Carrier Service httpx.AsyncClient")
        _client = None


# ============================================================================
# Helper Functions
# ============================================================================


def _build_headers(
    auth_header: Optional[str] = None,
    request_id: Optional[str] = None
) -> Dict[str, str]:
    """Build request headers with optional Authorization and x-request-id."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    if auth_header:
        headers["Authorization"] = auth_header
    
    if request_id:
        headers["x-request-id"] = request_id
    
    return headers


def is_endpoint_missing(e: HTTPException) -> bool:
    """
    Check if an HTTPException indicates a missing/unimplemented endpoint.
    
    Args:
        e: HTTPException raised by service client
    
    Returns:
        True if status code indicates missing endpoint (404, 405, 501)
    """
    return e.status_code in (
        status.HTTP_404_NOT_FOUND,
        status.HTTP_405_METHOD_NOT_ALLOWED,
        status.HTTP_501_NOT_IMPLEMENTED
    )


def _handle_http_error(e: httpx.HTTPStatusError) -> None:
    """
    Map httpx HTTP errors to FastAPI HTTPException.
    Logs full error server-side, exposes only safe messages.
    """
    status_code = e.response.status_code
    
    # Extract error message for logging
    try:
        error_data = e.response.json()
        error_message = error_data.get("message") or error_data.get("detail") or str(error_data)
    except Exception:
        error_message = e.response.text or f"Status {status_code}"
    
    # Log full error server-side
    logger.warning(f"Carrier service error {status_code}: {error_message}")
    
    # Map to safe user-facing messages
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
            detail="Carrier not found"
        )
    elif status_code == 405:
        raise HTTPException(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            detail="Endpoint not available"
        )
    elif status_code == 422:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid request"
        )
    elif status_code == 501:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Endpoint not implemented"
        )
    elif status_code >= 500:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Carrier service unavailable"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Carrier service error"
        )


def _handle_connection_error(e: Exception) -> None:
    """Handle connection errors (timeout, network issues, etc.)."""
    logger.error(f"Carrier service connection error: {type(e).__name__}: {e}")
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Cannot connect to carrier service: {type(e).__name__}"
    )


def safe_int(value: Any, default: int = 0) -> int:
    """
    Safely convert value to int, returning default on error.
    Handles None, empty strings, non-numeric strings gracefully.
    """
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert value to float, returning default on error.
    Handles None, empty strings, non-numeric strings gracefully.
    """
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _normalize_stats(data: Any) -> Dict[str, Any]:
    """
    Normalize carrier stats to consistent format.
    
    Returns standardized fields:
    - total_bookings: int
    - completed_bookings: int
    - cancelled_bookings: int
    - no_shows: int
    - late_arrivals: int
    - avg_delay_minutes: float
    - avg_dwell_minutes: float
    - anomaly_count: int
    - last_activity_at: str
    """
    if not isinstance(data, dict):
        return _empty_stats()
    
    stats = data.get("data", data)
    
    return {
        "total_bookings": safe_int(stats.get("total_bookings") or stats.get("totalBookings")),
        "completed_bookings": safe_int(stats.get("completed_bookings") or stats.get("completedBookings")),
        "cancelled_bookings": safe_int(stats.get("cancelled_bookings") or stats.get("cancelledBookings")),
        "no_shows": safe_int(stats.get("no_shows") or stats.get("noShows")),
        "late_arrivals": safe_int(stats.get("late_arrivals") or stats.get("lateArrivals")),
        "avg_delay_minutes": safe_float(stats.get("avg_delay_minutes") or stats.get("avgDelayMinutes")),
        "avg_dwell_minutes": safe_float(stats.get("avg_dwell_minutes") or stats.get("avgDwellMinutes")),
        "anomaly_count": safe_int(stats.get("anomaly_count") or stats.get("anomalyCount")),
        "last_activity_at": str(stats.get("last_activity_at") or stats.get("lastActivityAt") or "N/A")
    }


def _empty_stats() -> Dict[str, Any]:
    """Return empty stats structure."""
    return {
        "total_bookings": 0,
        "completed_bookings": 0,
        "cancelled_bookings": 0,
        "no_shows": 0,
        "late_arrivals": 0,
        "avg_delay_minutes": 0.0,
        "avg_dwell_minutes": 0.0,
        "anomaly_count": 0,
        "last_activity_at": "N/A"
    }


# ============================================================================
# Public API Functions
# ============================================================================


async def get_carrier_profile(
    carrier_id: str,
    auth_header: Optional[str] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get carrier profile information.
    
    Args:
        carrier_id: Carrier identifier
        auth_header: Optional Authorization header
        request_id: Optional request ID for tracing
    
    Returns:
        Carrier profile dict
    
    Raises:
        HTTPException: On backend errors
    """
    url = f"{CARRIER_SERVICE_URL}{CARRIER_PROFILE_PATH}".format(carrier_id=carrier_id)
    headers = _build_headers(auth_header, request_id)
    
    logger.debug(f"Fetching carrier profile for {carrier_id}")
    
    try:
        client = get_client()
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Retrieved carrier profile for {carrier_id}")
        return data
    except httpx.HTTPStatusError as e:
        _handle_http_error(e)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
        _handle_connection_error(e)
    except Exception as e:
        logger.exception(f"Unexpected error fetching carrier profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {type(e).__name__}"
        )


async def get_carrier_stats(
    carrier_id: str,
    window_days: int = 90,
    auth_header: Optional[str] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get carrier performance statistics.
    
    Args:
        carrier_id: Carrier identifier
        window_days: Statistics time window in days (default: 90)
        auth_header: Optional Authorization header
        request_id: Optional request ID for tracing
    
    Returns:
        Normalized stats dict with fields:
        - total_bookings, completed_bookings, cancelled_bookings
        - no_shows, late_arrivals
        - avg_delay_minutes, avg_dwell_minutes
        - anomaly_count, last_activity_at
    
    Raises:
        HTTPException: On backend errors
    """
    url = f"{CARRIER_SERVICE_URL}{CARRIER_STATS_PATH}".format(carrier_id=carrier_id)
    headers = _build_headers(auth_header, request_id)
    params = {"window_days": window_days}
    
    logger.debug(f"Fetching carrier stats for {carrier_id} (window={window_days} days)")
    
    try:
        client = get_client()
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        normalized = _normalize_stats(data)
        logger.info(f"Retrieved carrier stats for {carrier_id}: {normalized['total_bookings']} bookings")
        return normalized
    except httpx.HTTPStatusError as e:
        _handle_http_error(e)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
        _handle_connection_error(e)
    except Exception as e:
        logger.exception(f"Unexpected error fetching carrier stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {type(e).__name__}"
        )
