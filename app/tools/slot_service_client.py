"""
Slot Service HTTP Client

Provides async interface to the Slot Service backend for availability and calendar data.
Uses module-level singleton AsyncClient for efficient connection pooling.

Functions:
- get_availability: Get available slots for a specific terminal/date/gate
- get_calendar: Get slot calendar for a date range
- is_endpoint_missing: Check if HTTPException indicates missing endpoint
- aclose_client: Close HTTP client (call during shutdown)

All functions forward Authorization headers and handle common HTTP errors.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import date
import httpx
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

SLOT_SERVICE_URL = os.getenv("SLOT_SERVICE_URL", "http://localhost:3003")

# Endpoint paths
SLOT_AVAILABILITY_PATH = os.getenv("SLOT_AVAILABILITY_PATH", "/slots/availability")
SLOT_CALENDAR_PATH = os.getenv("SLOT_CALENDAR_PATH", "/slots/calendar")

# HTTP client config
REQUEST_TIMEOUT = float(os.getenv("SLOT_CLIENT_TIMEOUT", "15.0"))
MAX_CONNECTIONS = int(os.getenv("SLOT_CLIENT_MAX_CONNECTIONS", "100"))
MAX_KEEPALIVE_CONNECTIONS = int(os.getenv("SLOT_CLIENT_MAX_KEEPALIVE", "20"))

logger.info(f"Slot Service client configured with URL: {SLOT_SERVICE_URL}")


# ============================================================================
# Module-level HTTP Client
# ============================================================================

_client: Optional[httpx.AsyncClient] = None


def get_client() -> httpx.AsyncClient:
    """Get or create module-level httpx.AsyncClient singleton."""
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
        logger.info("Initialized Slot Service httpx.AsyncClient")
    
    return _client


async def aclose_client() -> None:
    """Close module-level httpx.AsyncClient gracefully."""
    global _client
    
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        logger.info("Closed Slot Service httpx.AsyncClient")
        _client = None


# ============================================================================
# Helpers
# ============================================================================


def _build_headers(
    auth_header: Optional[str] = None,
    request_id: Optional[str] = None
) -> Dict[str, str]:
    """Build request headers."""
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
    """Check if HTTPException indicates missing endpoint."""
    return e.status_code in (
        status.HTTP_404_NOT_FOUND,
        status.HTTP_405_METHOD_NOT_ALLOWED,
        status.HTTP_501_NOT_IMPLEMENTED
    )


def _handle_http_error(e: httpx.HTTPStatusError) -> None:
    """Map httpx HTTP errors to safe HTTPException."""
    status_code = e.response.status_code
    
    try:
        error_data = e.response.json()
        error_message = error_data.get("message") or error_data.get("detail") or str(error_data)
    except Exception:
        error_message = e.response.text or f"Status {status_code}"
    
    logger.warning(f"Slot service error {status_code}: {error_message}")
    
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
            detail="Resource not found"
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
            detail="Slot service unavailable"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slot service error"
        )


def _handle_connection_error(e: Exception) -> None:
    """Handle connection errors."""
    logger.error(f"Slot service connection error: {type(e).__name__}: {e}")
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Cannot connect to slot service: {type(e).__name__}"
    )


def _normalize_slot(slot: Any) -> Dict[str, Any]:
    """
    Normalize slot to consistent format.
    
    Required fields:
    - slot_id, start, end, capacity, remaining, terminal, gate
    """
    if not isinstance(slot, dict):
        return {}
    
    return {
        "slot_id": str(slot.get("slot_id") or slot.get("slotId") or slot.get("id") or ""),
        "start": str(slot.get("start") or slot.get("startTime") or slot.get("start_time") or ""),
        "end": str(slot.get("end") or slot.get("endTime") or slot.get("end_time") or ""),
        "capacity": int(slot.get("capacity") or slot.get("totalCapacity") or 0),
        "remaining": int(slot.get("remaining") or slot.get("remainingCapacity") or slot.get("available") or 0),
        "terminal": str(slot.get("terminal") or ""),
        "gate": str(slot.get("gate") or "")
    }


# ============================================================================
# Public API
# ============================================================================


async def get_availability(
    terminal: str,
    date: str,  # YYYY-MM-DD
    gate: Optional[str] = None,
    auth_header: Optional[str] = None,
    request_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get available slots for terminal/date.
    
    Args:
        terminal: Terminal identifier (A, B, C, etc.)
        date: Date in YYYY-MM-DD format
        gate: Optional gate filter
        auth_header: Optional Authorization header
        request_id: Optional request ID
    
    Returns:
        List of normalized slot dicts
    
    Raises:
        HTTPException: On backend errors
    """
    url = f"{SLOT_SERVICE_URL}{SLOT_AVAILABILITY_PATH}"
    headers = _build_headers(auth_header, request_id)
    params = {"terminal": terminal, "date": date}
    if gate:
        params["gate"] = gate
    
    logger.debug(f"Fetching slot availability for {terminal} on {date}")
    
    try:
        client = get_client()
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Extract slots from response
        if isinstance(data, dict):
            slots = data.get("data") or data.get("slots") or []
        elif isinstance(data, list):
            slots = data
        else:
            slots = []
        
        # Normalize and filter out empty slots (missing slot_id or start time)
        normalized = [_normalize_slot(s) for s in slots]
        valid_slots = [s for s in normalized if s.get("slot_id") and s.get("start")]
        
        logger.info(f"Retrieved {len(valid_slots)} valid slots for {terminal} (filtered from {len(normalized)} total)")
        return valid_slots
        
    except httpx.HTTPStatusError as e:
        _handle_http_error(e)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
        _handle_connection_error(e)
    except Exception as e:
        logger.exception(f"Unexpected error fetching availability: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {type(e).__name__}"
        )


async def get_calendar(
    terminal: str,
    date_from: str,  # YYYY-MM-DD
    date_to: str,  # YYYY-MM-DD
    auth_header: Optional[str] = None,
    request_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get slot calendar for date range.
    
    Args:
        terminal: Terminal identifier
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        auth_header: Optional Authorization header
        request_id: Optional request ID
    
    Returns:
        List of normalized slot dicts
    
    Raises:
        HTTPException: On backend errors
    """
    url = f"{SLOT_SERVICE_URL}{SLOT_CALENDAR_PATH}"
    headers = _build_headers(auth_header, request_id)
    params = {
        "terminal": terminal,
        "date_from": date_from,
        "date_to": date_to
    }
    
    logger.debug(f"Fetching slot calendar for {terminal} from {date_from} to {date_to}")
    
    try:
        client = get_client()
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Extract slots
        if isinstance(data, dict):
            slots = data.get("data") or data.get("slots") or []
        elif isinstance(data, list):
            slots = data
        else:
            slots = []
        
        # Normalize and filter out empty slots
        normalized = [_normalize_slot(s) for s in slots]
        valid_slots = [s for s in normalized if s.get("slot_id") and s.get("start")]
        
        logger.info(f"Retrieved {len(valid_slots)} valid slots for calendar (filtered from {len(normalized)} total)")
        return valid_slots
        
    except httpx.HTTPStatusError as e:
        _handle_http_error(e)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
        _handle_connection_error(e)
    except Exception as e:
        logger.exception(f"Unexpected error fetching calendar: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {type(e).__name__}"
        )
