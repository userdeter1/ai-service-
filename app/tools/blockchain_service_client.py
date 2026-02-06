"""
Blockchain Audit Service HTTP Client

Provides async interface to the Blockchain Audit Service backend for audit trail verification.
Uses a module-level singleton AsyncClient for efficient connection pooling.

Functions:
- verify_audit: Verify audit trail for booking/transaction
- record_audit: Record audit event on blockchain
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

BLOCKCHAIN_AUDIT_SERVICE_URL = os.getenv("BLOCKCHAIN_AUDIT_SERVICE_URL", "http://localhost:3010")

# Endpoint paths (configurable via env)
BLOCKCHAIN_VERIFY_PATH = os.getenv("BLOCKCHAIN_VERIFY_PATH", "/audit/verify")
BLOCKCHAIN_RECORD_PATH = os.getenv("BLOCKCHAIN_RECORD_PATH", "/audit/record")

# HTTP client timeout (seconds)
REQUEST_TIMEOUT = float(os.getenv("BLOCKCHAIN_CLIENT_TIMEOUT", "10.0"))

# Connection pool limits
MAX_CONNECTIONS = int(os.getenv("BLOCKCHAIN_CLIENT_MAX_CONNECTIONS", "50"))
MAX_KEEPALIVE_CONNECTIONS = int(os.getenv("BLOCKCHAIN_CLIENT_MAX_KEEPALIVE", "10"))

logger.info(f"Blockchain Audit Service client configured with URL: {BLOCKCHAIN_AUDIT_SERVICE_URL}")


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
            follow_redirects=False
        )
        logger.info("Initialized Blockchain Audit Service httpx.AsyncClient with connection pooling")
    
    return _client


async def aclose_client() -> None:
    """
    Close the module-level httpx.AsyncClient gracefully.
    Should be called during FastAPI shutdown (lifespan).
    """
    global _client
    
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        logger.info("Closed Blockchain Audit Service httpx.AsyncClient")
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


def is_endpoint_missing(e: HTTPException) -> bool:
    """
    Check if HTTPException indicates endpoint not implemented/found.
    
    Args:
        e: HTTPException to check
    
    Returns:
        True if status code is 404, 405, or 501
    """
    return e.status_code in (404, 405, 501)


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
    logger.warning(f"Blockchain audit service error {status_code}: {error_message}")
    
    # Map status codes to SAFE user-facing messages
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
            detail="Audit record not found"
        )
    elif status_code == 405:
        raise HTTPException(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            detail="Method not allowed"
        )
    elif status_code == 422:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid request"
        )
    elif status_code == 501:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Blockchain audit not implemented"
        )
    elif status_code >= 500:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Blockchain audit service unavailable"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Blockchain audit service error"
        )


def _handle_connection_error(e: Exception) -> None:
    """
    Handle connection errors (timeout, network issues, etc.).
    
    Raises:
        HTTPException with 503 status
    """
    logger.error(f"Blockchain audit service connection error: {type(e).__name__}: {e}")
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Cannot connect to blockchain audit service: {type(e).__name__}"
    )


# ============================================================================
# Public API Functions
# ============================================================================


async def verify_audit(
    booking_ref: Optional[str] = None,
    transaction_id: Optional[str] = None,
    auth_header: Optional[str] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Verify audit trail for booking or transaction on blockchain.
    
    Args:
        booking_ref: Optional booking reference to verify
        transaction_id: Optional transaction ID to verify
        auth_header: Optional Authorization header to forward
        request_id: Optional request ID for tracing
    
    Returns:
        Audit verification result dict:
        {
            "verified": bool,
            "booking_ref": str,
            "transaction_id": str,
            "hash": str,
            "timestamp": str,
            "chain_id": str,
            "contract_address": str,
            "tx_hash": str,
            "block_number": int,
            "details": {}
        }
    
    Raises:
        HTTPException: On backend errors (401, 403, 404, 503, etc.)
    """
    url = f"{BLOCKCHAIN_AUDIT_SERVICE_URL}{BLOCKCHAIN_VERIFY_PATH}"
    headers = _build_headers(auth_header, request_id)
    
    # Build query params
    params = {}
    if booking_ref:
        params["booking_ref"] = booking_ref
    if transaction_id:
        params["transaction_id"] = transaction_id
    
    logger.debug(f"Verifying blockchain audit for params: {params}")
    
    try:
        client = get_client()
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Normalize response
        audit_data = data.get("data", data)
        
        logger.info(f"Blockchain audit verified: {audit_data.get('verified', False)}")
        return audit_data
    except httpx.HTTPStatusError as e:
        _handle_http_error(e)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
        _handle_connection_error(e)
    except Exception as e:
        logger.exception(f"Unexpected error verifying blockchain audit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {type(e).__name__}"
        )


async def record_audit(
    event: Dict[str, Any],
    auth_header: Optional[str] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Record audit event on blockchain.
    
    Args:
        event: Audit event data dict containing:
            - event_type: str (e.g., "booking_created", "booking_updated")
            - ref: str (booking_ref or transaction_id)
            - data: dict (event data)
            - timestamp: str (ISO timestamp)
        auth_header: Optional Authorization header to forward
        request_id: Optional request ID for tracing
    
    Returns:
        Recording result dict:
        {
            "recorded": bool,
            "tx_hash": str,
            "block_number": int,
            "contract_address": str,
            "chain_id": str,
            "timestamp": str
        }
    
    Raises:
        HTTPException: On backend errors (401, 403, 503, etc.)
    """
    url = f"{BLOCKCHAIN_AUDIT_SERVICE_URL}{BLOCKCHAIN_RECORD_PATH}"
    headers = _build_headers(auth_header, request_id)
    
    logger.debug(f"Recording blockchain audit event: {event.get('event_type')}")
    
    try:
        client = get_client()
        response = await client.post(url, json=event, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Normalize response
        record_data = data.get("data", data)
        
        logger.info(f"Blockchain audit recorded: tx_hash={record_data.get('tx_hash')}")
        return record_data
    except httpx.HTTPStatusError as e:
        _handle_http_error(e)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
        _handle_connection_error(e)
    except Exception as e:
        logger.exception(f"Unexpected error recording blockchain audit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {type(e).__name__}"
        )
