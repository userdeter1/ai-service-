"""
Analytics Data Client

Aggregates data from multiple backend services for analytics computations.
Uses module-level singleton AsyncClient for efficient connection pooling.

Functions:
- get_bookings_summary: Get booking counts by status for date range
- get_capacity_data: Get slot capacity and remaining for terminals
- get_traffic_forecast: Get traffic forecast data (if available)
- get_recent_anomalies: Get recent anomaly events
- aclose_client: Close HTTP client (call during shutdown)

All functions handle REAL→MVP fallback gracefully.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, date, timedelta
import httpx
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# Primary data source (use existing service clients preferred)
ANALYTICS_DATA_SOURCE = os.getenv("ANALYTICS_DATA_SOURCE", "nestjs")

# Booking summary endpoint (configurable)
BOOKINGS_SUMMARY_PATH = os.getenv("BOOKINGS_SUMMARY_PATH", "/bookings/summary")

# HTTP client config
REQUEST_TIMEOUT = float(os.getenv("ANALYTICS_CLIENT_TIMEOUT", "15.0"))
MAX_CONNECTIONS = int(os.getenv("ANALYTICS_CLIENT_MAX_CONNECTIONS", "50"))
MAX_KEEPALIVE_CONNECTIONS = int(os.getenv("ANALYTICS_CLIENT_MAX_KEEPALIVE", "10"))

logger.info(f"Analytics Data client configured (source: {ANALYTICS_DATA_SOURCE})")


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
        logger.info("Initialized Analytics Data httpx.AsyncClient")
    
    return _client


async def aclose_client() -> None:
    """Close module-level httpx.AsyncClient gracefully."""
    global _client
    
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        logger.info("Closed Analytics Data httpx.AsyncClient")
        _client = None


# ============================================================================
# Data Aggregation Functions
# ============================================================================


async def get_bookings_summary(
    terminal: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    auth_header: Optional[str] = None,
    trace_id: str = "unknown"
) -> Dict[str, Any]:
    """
    Get booking summary (counts by status) for analytics.
    
    Args:
        terminal: Terminal filter (A, B, C, etc.)
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        auth_header: Authorization header
        trace_id: Request trace ID
    
    Returns:
        {
            "total": int,
            "by_status": {"confirmed": N, "pending": M, ...},
            "by_terminal": {"A": N, "B": M, ...},
            "data_quality": "real|mvp"
        }
    """
    logger.info(f"[{trace_id[:8]}] Fetching bookings summary")
    
    try:
        # Try using existing booking_service_client
        from app.tools.booking_service_client import get_client as get_booking_client, BOOKING_SERVICE_URL
        
        # Build query params
        params = {}
        if terminal:
            params["terminal"] = terminal
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        
        headers = {"Accept": "application/json"}
        if auth_header:
            headers["Authorization"] = auth_header
        if trace_id:
            headers["x-request-id"] = trace_id[:8]
        
        # Try summary endpoint first
        url = f"{BOOKING_SERVICE_URL}{BOOKINGS_SUMMARY_PATH}"
        
        client = get_booking_client()
        response = await client.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            result = data.get("data", data)
            result["data_quality"] = "real"
            logger.info(f"[{trace_id[:8]}] Got bookings summary (real mode)")
            return result
        
    except Exception as e:
        logger.debug(f"[{trace_id[:8]}] Real bookings summary failed: {e}")
    
    # MVP Fallback: Return approximate data
    logger.info(f"[{trace_id[:8]}] Using MVP fallback for bookings summary")
    
    return {
        "total": 0,
        "by_status": {
            "confirmed": 0,
            "pending": 0,
            "cancelled": 0
        },
        "by_terminal": {terminal: 0} if terminal else {},
        "data_quality": "mvp",
        "note": "Bookings summary endpoint not available - using estimates"
    }


async def get_capacity_data(
    terminal: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    auth_header: Optional[str] = None,
    trace_id: str = "unknown"
) -> Dict[str, Any]:
    """
    Get slot capacity data for analytics.
    
    Args:
        terminal: Terminal filter
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        auth_header: Authorization header
        trace_id: Request trace ID
    
    Returns:
        {
            "total_capacity": int,
            "total_remaining": int,
            "utilization": float (0-1),
            "by_terminal": {...},
            "data_quality": "real|mvp"
        }
    """
    logger.info(f"[{trace_id[:8]}] Fetching capacity data")
    
    try:
        # Use slot_service_client
        from app.tools.slot_service_client import get_availability
        
        # Get availability for terminal/date
        target_date = date_from or date.today().isoformat()
        
        slots = await get_availability(
            terminal=terminal,
            target_date=target_date,
            gate=None,
            auth_header=auth_header,
            request_id=trace_id[:8]
        )
        
        # Aggregate capacity data
        total_capacity = 0
        total_remaining = 0
        
        for slot in slots:
            capacity = slot.get("capacity", 0)
            remaining = slot.get("remaining", 0)
            total_capacity += capacity
            total_remaining += remaining
        
        utilization = 1.0 - (total_remaining / total_capacity) if total_capacity > 0 else 0.0
        
        result = {
            "total_capacity": total_capacity,
            "total_remaining": total_remaining,
            "utilization": round(utilization, 3),
            "by_terminal": {terminal: {"capacity": total_capacity, "remaining": total_remaining}} if terminal else {},
            "data_quality": "real"
        }
        
        logger.info(f"[{trace_id[:8]}] Got capacity data (real mode): {total_remaining}/{total_capacity}")
        return result
        
    except Exception as e:
        logger.debug(f"[{trace_id[:8]}] Real capacity data failed: {e}")
    
    # MVP Fallback
    logger.info(f"[{trace_id[:8]}] Using MVP fallback for capacity data")
    
    return {
        "total_capacity": 100,
        "total_remaining": 30,
        "utilization": 0.70,
        "by_terminal": {terminal: {"capacity": 100, "remaining": 30}} if terminal else {},
        "data_quality": "mvp",
        "note": "Slot service not available - using estimates"
    }


async def get_traffic_forecast(
    terminal: Optional[str] = None,
    target_date: Optional[str] = None,
    auth_header: Optional[str] = None,
    trace_id: str = "unknown"
) -> Dict[str, Any]:
    """
    Get traffic forecast data (if available).
    
    Args:
        terminal: Terminal filter
        target_date: Target date (YYYY-MM-DD)
        auth_header: Authorization header
        trace_id: Request trace ID
    
    Returns:
        {
            "intensity": float (0-1),
            "peak_hour": str,
            "forecast": [...],
            "data_quality": "real|mvp"
        }
    """
    logger.info(f"[{trace_id[:8]}] Fetching traffic forecast")
    
    try:
        # Try nest_client for traffic data
        from app.tools.nest_client import get_client as get_nest_client, NEST_BASE_URL
        
        headers = {"Accept": "application/json"}
        if auth_header:
            headers["Authorization"] = auth_header
        headers["x-request-id"] = trace_id[:8]
        
        params = {}
        if terminal:
            params["terminal"] = terminal
        if target_date:
            params["date"] = target_date
        
        client = get_nest_client()
        response = await client.get(
            f"{NEST_BASE_URL}/traffic/forecast",
            params=params,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            result = data.get("data", data)
            result["data_quality"] = "real"
            logger.info(f"[{trace_id[:8]}] Got traffic forecast (real mode)")
            return result
            
    except Exception as e:
        logger.debug(f"[{trace_id[:8]}] Real traffic forecast failed: {e}")
    
    # MVP Fallback: Use heuristics based on time of day
    logger.info(f"[{trace_id[:8]}] Using MVP fallback for traffic forecast")
    
    current_hour = datetime.now().hour
    
    # Peak hours: 8-10am and 2-4pm
    if (8 <= current_hour <= 10) or (14 <= current_hour <= 16):
        intensity = 0.75
        peak_hour = "09:00" if current_hour < 12 else "15:00"
    elif (6 <= current_hour <= 7) or (11 <= current_hour <= 13) or (17 <= current_hour <= 18):
        intensity = 0.50
        peak_hour = "09:00"
    else:
        intensity = 0.25
        peak_hour = "09:00"
    
    return {
        "intensity": intensity,
        "peak_hour": peak_hour,
        "forecast": [],
        "data_quality": "mvp",
        "note": "Traffic forecast not available - using time-of-day heuristic"
    }


async def get_recent_anomalies(
    terminal: Optional[str] = None,
    target_date: Optional[str] = None,
    hours: int = 6,
    auth_header: Optional[str] = None,
    trace_id: str = "unknown"
) -> Dict[str, Any]:
    """
    Get recent anomaly events for analytics.
    
    Args:
        terminal: Terminal filter
        target_date: Target date (YYYY-MM-DD)
        hours: Lookback window in hours
        auth_header: Authorization header
        trace_id: Request trace ID
    
    Returns:
        {
            "count": int,
            "severity_avg": float (0-1),
            "anomalies": [...],
            "data_quality": "real|mvp"
        }
    """
    logger.info(f"[{trace_id[:8]}] Fetching recent anomalies")
    
    try:
        # Try nest_client for anomaly data
        from app.tools.nest_client import get_client as get_nest_client, NEST_BASE_URL
        
        headers = {"Accept": "application/json"}
        if auth_header:
            headers["Authorization"] = auth_header
        headers["x-request-id"] = trace_id[:8]
        
        params = {"hours": hours}
        if terminal:
            params["terminal"] = terminal
        if target_date:
            params["date"] = target_date
        
        client = get_nest_client()
        response = await client.get(
            f"{NEST_BASE_URL}/anomalies/recent",
            params=params,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            anomalies = data.get("data", data).get("anomalies", [])
            
            count = len(anomalies)
            severities = [a.get("severity", 0.5) for a in anomalies if isinstance(a.get("severity"), (int, float))]
            severity_avg = sum(severities) / len(severities) if severities else 0.0
            
            result = {
                "count": count,
                "severity_avg": round(severity_avg, 3),
                "anomalies": anomalies[:10],  # Top 10 most recent
                "data_quality": "real"
            }
            
            logger.info(f"[{trace_id[:8]}] Got recent anomalies (real mode): {count} anomalies")
            return result
            
    except Exception as e:
        logger.debug(f"[{trace_id[:8]}] Real anomalies failed: {e}")
    
    # MVP Fallback
    logger.info(f"[{trace_id[:8]}] Using MVP fallback for anomalies")
    
    return {
        "count": 0,
        "severity_avg": 0.0,
        "anomalies": [],
        "data_quality": "mvp",
        "note": "Anomaly service not available - no recent anomalies detected"
    }
