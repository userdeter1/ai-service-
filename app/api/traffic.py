"""
Traffic API Endpoints

Traffic monitoring and forecasting endpoints.

Endpoints:
- GET /traffic/health - Health check (public)
- GET /traffic/forecast - Traffic forecast (ADMIN/OPERATOR only)

Note: Full traffic forecasting requires backend implementation.
"""

import logging
import uuid
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Request, status, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/traffic", tags=["traffic"])

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

@router.get("/health")
async def get_traffic_health(request: Request):
    """
    Traffic service health check.
    
    **Public access allowed**
    """
    trace_id = get_trace_id(request)
    
    return standard_response(
        message="Traffic service is operational",
        data={
            "status": "ok",
            "service": "traffic"
        },
        trace_id=trace_id
    )


@router.get("/forecast")
async def get_traffic_forecast(
    request: Request,
    terminal: Optional[str] = Query(None, description="Terminal filter (optional)"),
    date: Optional[str] = Query(None, description="Date for forecast (YYYY-MM-DD, optional, defaults to tomorrow)"),
    horizon_hours: int = Query(24, description="Forecast horizon in hours", ge=1, le=168)
):
    """
    Get traffic forecast.
    
    Returns predicted traffic levels for the specified terminal and time range.
    
    **Requires**: ADMIN or OPERATOR role
    
    **Note**: This endpoint requires backend traffic forecasting service.
    If not configured, returns a safe "not implemented" response.
    """
    require_operator_or_admin(request)
    trace_id = get_trace_id(request)
    auth_header = get_auth_header(request)
    
    # Check if traffic model exists
    try:
        from app.models.loader import get_model, list_models
        
        available_models = list_models()
        
        # Check if traffic_model is available
        if "traffic_model" in available_models and available_models["traffic_model"].get("available"):
            model = get_model("traffic_model")
            
            # Call model predict
            result = await model.predict(
                input={
                    "terminal": terminal,
                    "date": date,
                    "horizon_hours": horizon_hours
                },
                context={
                    "auth_header": auth_header,
                    "trace_id": trace_id,
                    "user_role": get_role(request)
                }
            )
            
            if result.get("ok"):
                forecast_data = result["result"]
                proofs = result.get("proofs", {})
                
                return standard_response(
                    message="Traffic forecast generated",
                    data=forecast_data,
                    proofs=proofs,
                    trace_id=trace_id
                )
        
        # Model not available or not implemented
        return standard_response(
            message="Traffic forecasting feature not yet implemented",
            data={
                "status": "not_implemented",
                "reason": "Backend traffic forecasting service not configured",
                "suggested_action": "Check back later or contact system administrator"
            },
            proofs={
                "trace_id": trace_id,
                "feature": "traffic_forecast",
                "status": "planned"
            },
            trace_id=trace_id
        )
        
    except Exception as e:
        logger.exception(f"[{trace_id[:8]}] Traffic forecast error: {e}")
        
        # Return safe "not implemented" instead of error
        return standard_response(
            message="Traffic forecasting feature not yet available",
            data={
                "status": "unavailable",
                "reason": "Backend service not configured"
            },
            proofs={
                "trace_id": trace_id,
                "feature": "traffic_forecast"
            },
            trace_id=trace_id
        )
