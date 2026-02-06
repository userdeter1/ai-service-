"""
Operator API Endpoints

Operational endpoints for booking status checks and slot availability.

Endpoints:
- GET /operator/bookings/{booking_ref}/status - Get booking status
- POST /operator/bookings/status/batch - Get multiple booking statuses
- GET /operator/slots/availability - Get slot availability

All endpoints require ADMIN or OPERATOR role.
"""

import logging
import uuid
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, HTTPException, Request, status, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/operator", tags=["operator"])

# ============================================================================
# Schemas
# ============================================================================

class BatchStatusRequest(BaseModel):
    """Request body for batch status check."""
    refs: List[str] = Field(..., description="List of booking references")


# ============================================================================
# Utilities
# ============================================================================

def get_trace_id(request: Request) -> str:
    """Extract or generate trace ID from request."""
    return request.headers.get("x-request-id", str(uuid.uuid4()))


def get_auth_header(request: Request) -> Optional[str]:
    """Extract Authorization header."""
    return request.headers.get("authorization")


def get_role(request: Request) -> str:
    """Extract user role from headers."""
    return request.headers.get("x-user-role", "ANON").upper().strip()


def require_operator_or_admin(request: Request) -> None:
    """Require ADMIN or OPERATOR role, raise 403 if not."""
    role = get_role(request)
    if role not in ("ADMIN", "OPERATOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operator or Admin access required (your role: {role})"
        )


def standard_response(
    message: str,
    data: Optional[Dict[str, Any]] = None,
    proofs: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """Build standard response format."""
    return {
        "message": message,
        "data": data or {},
        "proofs": proofs or {"trace_id": trace_id}
    }


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/bookings/{booking_ref}/status")
async def get_booking_status(
    booking_ref: str,
    request: Request
):
    """
    Get booking status by reference.
    
    **Requires**: ADMIN or OPERATOR role
    """
    require_operator_or_admin(request)
    trace_id = get_trace_id(request)
    auth_header = get_auth_header(request)
    
    try:
        from app.tools.booking_service_client import get_booking_status
        
        booking = await get_booking_status(
            booking_ref=booking_ref,
            auth_header=auth_header,
            request_id=trace_id[:8]
        )
        
        return standard_response(
            message=f"Booking {booking_ref} status retrieved",
            data=booking,
            trace_id=trace_id
        )
        
    except HTTPException as e:
        # Pass through HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"[{trace_id[:8]}] Failed to get booking status: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to retrieve booking status"
        )


@router.post("/bookings/status/batch")
async def get_batch_status(
    body: BatchStatusRequest,
    request: Request
):
    """
    Get status for multiple bookings.
    
    **Requires**: ADMIN or OPERATOR role
    """
    require_operator_or_admin(request)
    trace_id = get_trace_id(request)
    auth_header = get_auth_header(request)
    
    if not body.refs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one booking reference is required"
        )
    
    if len(body.refs) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 100 booking references allowed per request"
        )
    
    try:
        from app.tools.booking_service_client import get_bookings_batch
        
        bookings = await get_bookings_batch(
            booking_refs=body.refs,
            auth_header=auth_header,
            request_id=trace_id[:8]
        )
        
        return standard_response(
            message=f"Retrieved status for {len(bookings)} bookings",
            data={
                "bookings": bookings,
                "requested_count": len(body.refs),
                "retrieved_count": len(bookings)
            },
            trace_id=trace_id
        )
        
    except HTTPException as e:
        raise
    except Exception as e:
        logger.exception(f"[{trace_id[:8]}] Failed to get batch status: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to retrieve batch booking status"
        )


@router.get("/slots/availability")
async def get_slot_availability(
    request: Request,
    terminal: str = Query(..., description="Terminal identifier (A, B, C, etc.)"),
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    gate: Optional[str] = Query(None, description="Optional gate filter")
):
    """
    Get slot availability for terminal and date.
    
    **Requires**: ADMIN or OPERATOR role
    """
    require_operator_or_admin(request)
    trace_id = get_trace_id(request)
    auth_header = get_auth_header(request)
    
    try:
        from app.tools.slot_service_client import get_availability
        
        slots = await get_availability(
            terminal=terminal,
            date=date,
            gate=gate,
            auth_header=auth_header,
            request_id=trace_id[:8]
        )
        
        return standard_response(
            message=f"Found {len(slots)} available slots for terminal {terminal} on {date}",
            data={
                "terminal": terminal,
                "date": date,
                "gate": gate,
                "slots": slots,
                "total_count": len(slots)
            },
            trace_id=trace_id
        )
        
    except HTTPException as e:
        raise
    except Exception as e:
        logger.exception(f"[{trace_id[:8]}] Failed to get slot availability: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to retrieve slot availability"
        )
