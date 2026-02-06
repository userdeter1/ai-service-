"""
Blockchain Tool

High-level wrapper for blockchain audit verification.
Supports multiple modes: service-based (default) or direct blockchain access.

Functions:
- verify_blockchain_integrity: Verify audit trail for booking/transaction
- record_blockchain_event: Record audit event (optional)
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Configuration
BLOCKCHAIN_MODE = os.getenv("BLOCKCHAIN_MODE", "service")  # "service" or "direct"


async def verify_blockchain_integrity(
    booking_ref: Optional[str] = None,
    transaction_id: Optional[str] = None,
    auth_header: Optional[str] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Verify blockchain audit trail for booking or transaction.
    
    REAL→MVP Strategy:
    1. Try blockchain_service_client (REAL)
    2. If service not configured/missing → return MVP "not_enabled" response
    3. Never fake verification - be honest about limitations
    
    Args:
        booking_ref: Optional booking reference to verify
        transaction_id: Optional transaction ID to verify
        auth_header: Optional Authorization header
        request_id: Optional request ID for tracing (replaces trace_id)
    
    Returns:
        Blockchain verification dict:
        {
            "verified": bool,
            "status": str ("verified"|"not_found"|"not_enabled"|"error"),
            "booking_ref": str,
            "transaction_id": str,
            "blockchain_hash": str (optional),
            "block_number": int (optional),
            "timestamp": str (optional),
            "chain": str (optional),
            "reason": str (optional),
            "required_setup": dict (optional, if not_enabled)
        }
    """
    trace_id = request_id or "unknown"
    logger.info(f"[{trace_id[:8]}] Verifying blockchain audit")
    
    # REAL: Try blockchain service client
    try:
        from app.tools.blockchain_service_client import (
            verify_audit,
            is_endpoint_missing,
            BLOCKCHAIN_AUDIT_SERVICE_URL,
            BLOCKCHAIN_VERIFY_PATH
        )
        from fastapi import HTTPException
        
        result = await verify_audit(
            booking_ref=booking_ref,
            transaction_id=transaction_id,
            auth_header=auth_header,
            request_id=trace_id[:8]
        )
        
        # Normalize REAL response to match schema
        normalized = {
            "verified": result.get("verified", False),
            "status": "verified" if result.get("verified") else "not_found",
            "booking_ref": booking_ref or result.get("booking_ref", ""),
            "transaction_id": transaction_id or result.get("transaction_id", ""),
        }
        
        # Add blockchain details if present
        if "tx_hash" in result:
            normalized["blockchain_hash"] = result["tx_hash"]
        if "hash" in result:
            normalized["blockchain_hash"] = result.get("blockchain_hash", result["hash"])
        if "block_number" in result:
            normalized["block_number"] = result["block_number"]
        if "timestamp" in result:
            normalized["timestamp"] = result["timestamp"]
        if "chain_id" in result:
            normalized["chain"] = result["chain_id"]
        
        logger.info(f"[{trace_id[:8]}] Blockchain verification complete: {normalized['status']}")
        return normalized
    
    except HTTPException as e:
        # Check if endpoint is missing/not implemented
        from app.tools.blockchain_service_client import is_endpoint_missing
        
        if is_endpoint_missing(e):
            logger.warning(f"[{trace_id[:8]}] Blockchain service endpoint not implemented")
            # Return MVP "not_enabled" response
            return _mvp_not_enabled_response(booking_ref, transaction_id, trace_id)
        
        # Other HTTP errors (auth, forbidden, etc.)
        logger.error(f"[{trace_id[:8]}] Blockchain service error: {e.status_code}")
        return {
            "verified": False,
            "status": "error",
            "booking_ref": booking_ref or "",
            "transaction_id": transaction_id or "",
            "reason": f"Blockchain service error: {e.detail}",
        }
    
    except ImportError as e:
        logger.warning(f"[{trace_id[:8]}] Blockchain service client not available: {e}")
        # Service client module doesn't exist
        return _mvp_not_enabled_response(booking_ref, transaction_id, trace_id)
    
    except Exception as e:
        # Network errors, timeouts, etc.
        logger.error(f"[{trace_id[:8]}] Blockchain verification failed: {type(e).__name__}: {e}")
        
        # Check if it's a connection error (service not running)
        if "connect" in str(e).lower() or "timeout" in str(e).lower():
            return _mvp_not_enabled_response(booking_ref, transaction_id, trace_id)
        
        # Other unexpected errors
        return {
            "verified": False,
            "status": "error",
            "booking_ref": booking_ref or "",
            "transaction_id": transaction_id or "",
            "reason": f"Verification failed: {type(e).__name__}",
        }


def _mvp_not_enabled_response(
    booking_ref: Optional[str],
    transaction_id: Optional[str],
    trace_id: str
) -> Dict[str, Any]:
    """
    Return MVP "not_enabled" response when blockchain service is unavailable.
    
    This is HONEST - we don't fake blockchain verification.
    """
    from app.tools.blockchain_service_client import (
        BLOCKCHAIN_AUDIT_SERVICE_URL,
        BLOCKCHAIN_VERIFY_PATH,
        BLOCKCHAIN_RECORD_PATH
    )
    
    logger.info(f"[{trace_id[:8]}] Blockchain audit not enabled (service unavailable)")
    
    return {
        "verified": False,
        "status": "not_enabled",
        "booking_ref": booking_ref or "",
        "transaction_id": transaction_id or "",
        "reason": "Blockchain audit service is not enabled or not available",
        "required_setup": {
            "service_url": BLOCKCHAIN_AUDIT_SERVICE_URL,
            "endpoints": {
                "verify": BLOCKCHAIN_VERIFY_PATH,
                "record": BLOCKCHAIN_RECORD_PATH
            },
            "env_vars": [
                "BLOCKCHAIN_AUDIT_SERVICE_URL",
                "BLOCKCHAIN_VERIFY_PATH (optional)",
                "BLOCKCHAIN_RECORD_PATH (optional)"
            ],
            "message": (
                "To enable blockchain audit verification, ensure the blockchain "
                "audit service is running and accessible at the configured URL. "
                "Alternatively, set BLOCKCHAIN_MODE=direct and configure blockchain RPC."
            )
        }
    }



async def record_blockchain_event(
    event_type: str,
    ref: str,
    data: Dict[str, Any],
    auth_header: Optional[str] = None,
    trace_id: str = "unknown"
) -> Dict[str, Any]:
    """
    Record audit event on blockchain (optional feature).
    
    Args:
        event_type: Event type (e.g., "booking_created", "booking_updated")
        ref: Booking reference or transaction ID
        data: Event data dict
        auth_header: Optional Authorization header
        trace_id: Request trace ID for logging
    
    Returns:
        Recording result dict:
        {
            "recorded": bool,
            "tx_hash": str,
            "block_number": int,
            "timestamp": str
        }
    """
    logger.info(f"[{trace_id[:8]}] Recording blockchain event: {event_type} for {ref}")
    
    try:
        from app.tools.blockchain_service_client import record_audit
        
        event = {
            "event_type": event_type,
            "ref": ref,
            "data": data,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        result = await record_audit(
            event=event,
            auth_header=auth_header,
            request_id=trace_id[:8]
        )
        
        logger.info(f"[{trace_id[:8]}] Blockchain event recorded: tx_hash={result.get('tx_hash')}")
        return result
    
    except Exception as e:
        logger.error(f"[{trace_id[:8]}] Failed to record blockchain event: {e}")
        raise
