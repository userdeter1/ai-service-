"""
Slots API Endpoints

Slot availability and recommendation endpoints.

Endpoints:
- GET /slots/availability - Get available slots (public + authenticated)
- POST /slots/recommend - Get recommended slots (authenticated only)

**Public access**: /slots/availability allowed without auth but returns limited data.
**Authenticated**: Full slot details + carrier-aware recommendations.
"""

import logging
import uuid
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Request, status, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slots", tags=["slots"])

# ============================================================================
# Schemas
# ============================================================================

class SlotRecommendationRequest(BaseModel):
    """Request body for slot recommendation."""
    terminal: str = Field(..., description="Terminal identifier (A, B, C, etc.)")
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    gate: Optional[str] = Field(None, description="Optional gate filter")
    carrier_id: Optional[str] = Field(None, description="Carrier ID for carrier-aware ranking")
    requested_time: Optional[str] = Field(None, description="Requested time (HH:MM or YYYY-MM-DD HH:MM:SS)")


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

@router.get("/availability")
async def get_availability(
    request: Request,
    terminal: str = Query(..., description="Terminal identifier (A, B, C, etc.)"),
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    gate: Optional[str] = Query(None, description="Optional gate filter")
):
    """
    Get slot availability.
    
    **Public access allowed** - Returns basic slot availability.
    If authenticated, returns full slot details.
    Does NOT compute carrier scoring for unauthenticated requests.
    """
    trace_id = get_trace_id(request)
    auth_header = get_auth_header(request)
    is_authenticated = auth_header is not None
    
    try:
        from app.tools.slot_service_client import get_availability as get_slots
        
        slots = await get_slots(
            terminal=terminal,
            date=date,
            gate=gate,
            auth_header=auth_header if is_authenticated else None,
            request_id=trace_id[:8]
        )
        
        # Build response with appropriate detail level
        response_data = {
            "terminal": terminal,
            "date": date,
            "gate": gate,
            "slots": slots,
            "total_count": len(slots)
        }
        
        # Add auth status to proofs
        proofs = {
            "trace_id": trace_id,
            "authenticated": is_authenticated
        }
        
        if not is_authenticated:
            proofs["note"] = "Limited data - authenticate for full details"
        
        return standard_response(
            message=f"Found {len(slots)} available slots for terminal {terminal} on {date}",
            data=response_data,
            proofs=proofs,
            trace_id=trace_id
        )
        
    except HTTPException as e:
        # If endpoint missing, return helpful error
        if e.status_code == 404 or e.status_code == 501:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Slot availability service not configured"
            )
        raise
    except Exception as e:
        logger.exception(f"[{trace_id[:8]}] Failed to get slot availability: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to retrieve slot availability"
        )


@router.post("/recommend")
async def recommend_slots(
    body: SlotRecommendationRequest,
    request: Request
):
    """
    Get recommended slots.
    
    Returns AI-powered slot recommendations based on:
    - Availability
    - Carrier reliability (if carrier_id provided)
    - Time preferences
    - Gate preferences
    
    **Requires authentication**
    """
    trace_id = get_trace_id(request)
    auth_header = get_auth_header(request)
    
    # Require authentication
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for slot recommendations"
        )
    
    try:
        from app.models.loader import get_model
        
        # Use model loader to get slot recommendation model
        model = get_model("slot_recommendation")
        
        # Prepare input
        model_input = {
            "terminal": body.terminal,
            "date": body.date,
            "gate": body.gate,
            "carrier_id": body.carrier_id,
            "requested_time": body.requested_time
        }
        
        # Build context
        context = {
            "auth_header": auth_header,
            "trace_id": trace_id,
            "user_role": get_role(request)
        }
        
        # Call model
        result = await model.predict(
            input=model_input,
            context=context
        )
        
        if not result.get("ok"):
            error = result.get("error", {})
            error_type = error.get("type", "ModelError")
            
            # Check if backend unavailable
            if error_type == "BackendUnavailable":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=error.get("message", "Slot recommendation service unavailable")
                )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error.get("message", "Failed to generate recommendations")
            )
        
        recommendation_data = result["result"]
        model_proofs = result.get("proofs", {})
        
        recommended_count = len(recommendation_data.get("recommended", []))
        
        return standard_response(
            message=f"Generated {recommended_count} slot recommendations",
            data=recommendation_data,
            proofs=model_proofs,
            trace_id=trace_id
        )
        
    except HTTPException as e:
        raise
    except Exception as e:
        logger.exception(f"[{trace_id[:8]}] Failed to generate recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to generate slot recommendations"
        )
