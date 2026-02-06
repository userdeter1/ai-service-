"""
Carriers API Endpoints

Carrier-related endpoints for statistics, scoring, and profiles.

Endpoints:
- GET /carriers/{carrier_id}/stats - Get carrier statistics
- GET /carriers/{carrier_id}/score - Get carrier reliability score
- GET /carriers/{carrier_id}/profile - Get carrier profile

RBAC: ADMIN/OPERATOR can access any carrier, CARRIER role can only access own data.
"""

import logging
import uuid
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Request, status, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/carriers", tags=["carriers"])

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


def get_carrier_id_from_headers(request: Request) -> Optional[str]:
    """Extract carrier_id from x-carrier-id header (for CARRIER role)."""
    return request.headers.get("x-carrier-id")


def check_carrier_access(request: Request, requested_carrier_id: str) -> None:
    """
    Check if user can access requested carrier data.
    
    - ADMIN/OPERATOR: can access any carrier
    - CARRIER: can only access own carrier_id (from x-carrier-id header)
    - Others: denied
    """
    role = get_role(request)
    
    if role in ("ADMIN", "OPERATOR"):
        # Full access
        return
    
    if role == "CARRIER":
        own_carrier_id = get_carrier_id_from_headers(request)
        if not own_carrier_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Carrier ID not found in headers"
            )
        
        if str(requested_carrier_id) != str(own_carrier_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access other carriers' data"
            )
        return
    
    # Default: deny
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Access denied for role: {role}"
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

@router.get("/carriers/{carrier_id}/stats")
async def get_carrier_stats(
    carrier_id: str,
    request: Request,
    window_days: int = Query(90, description="Historical window in days", ge=1, le=365)
):
    """
    Get carrier statistics.
    
    Returns normalized carrier performance statistics including
    bookings, completions, cancellations, no-shows, delays, etc.
    
    **RBAC**: ADMIN/OPERATOR can access any, CARRIER can only access own
    """
    check_carrier_access(request, carrier_id)
    trace_id = get_trace_id(request)
    auth_header = get_auth_header(request)
    
    try:
        from app.tools.carrier_service_client import get_carrier_stats
        
        stats = await get_carrier_stats(
            carrier_id=carrier_id,
            window_days=window_days,
            auth_header=auth_header,
            request_id=trace_id[:8]
        )
        
        return standard_response(
            message=f"Carrier {carrier_id} statistics retrieved",
            data={
                "carrier_id": carrier_id,
                "window_days": window_days,
                "stats": stats
            },
            trace_id=trace_id
        )
        
    except HTTPException as e:
        raise
    except Exception as e:
        logger.exception(f"[{trace_id[:8]}] Failed to get carrier stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to retrieve carrier statistics"
        )


@router.get("/carriers/{carrier_id}/score")
async def get_carrier_score(
    carrier_id: str,
    request: Request,
    window_days: int = Query(90, description="Historical window in days", ge=1, le=365)
):
    """
    Get carrier reliability score.
    
    Returns AI-computed reliability score (0-100), tier (A/B/C/D),
    confidence level, and component breakdown.
    
    **RBAC**: ADMIN/OPERATOR can access any, CARRIER can only access own
    """
    check_carrier_access(request, carrier_id)
    trace_id = get_trace_id(request)
    auth_header = get_auth_header(request)
    
    try:
        from app.models.loader import get_model
        
        # Use model loader to get carrier scoring model
        model = get_model("carrier_scoring")
        
        result = await model.predict(
            input={
                "carrier_id": carrier_id,
                "window_days": window_days
            },
            context={
                "auth_header": auth_header,
                "trace_id": trace_id,
                "user_role": get_role(request)
            }
        )
        
        if not result.get("ok"):
            error = result.get("error", {})
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error.get("message", "Failed to compute carrier score")
            )
        
        score_data = result["result"]
        model_proofs = result.get("proofs", {})
        
        return standard_response(
            message=f"Carrier {carrier_id} score: {score_data.get('score', 0):.1f}/100 (Tier {score_data.get('tier', 'N/A')})",
            data=score_data,
            proofs=model_proofs,
            trace_id=trace_id
        )
        
    except HTTPException as e:
        raise
    except Exception as e:
        logger.exception(f"[{trace_id[:8]}] Failed to get carrier score: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to compute carrier score"
        )


@router.get("/carriers/{carrier_id}/profile")
async def get_carrier_profile(
    carrier_id: str,
    request: Request
):
    """
    Get carrier profile.
    
    Returns basic carrier information (name, contact, status).
    
    **RBAC**: ADMIN/OPERATOR can access any, CARRIER can only access own
    """
    check_carrier_access(request, carrier_id)
    trace_id = get_trace_id(request)
    auth_header = get_auth_header(request)
    
    try:
        from app.tools.carrier_service_client import get_carrier_profile
        
        profile = await get_carrier_profile(
            carrier_id=carrier_id,
            auth_header=auth_header,
            request_id=trace_id[:8]
        )
        
        return standard_response(
            message=f"Carrier {carrier_id} profile retrieved",
            data={
                "carrier_id": carrier_id,
                "profile": profile
            },
            trace_id=trace_id
        )
        
    except HTTPException as e:
        raise
    except Exception as e:
        logger.exception(f"[{trace_id[:8]}] Failed to get carrier profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to retrieve carrier profile"
        )
