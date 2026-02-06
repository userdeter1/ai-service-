"""
Anomalies API Endpoints

Anomaly detection and monitoring endpoints.

Endpoints:
- GET /anomalies/health - Health check (public)
- GET /anomalies/recent - Get recent anomalies (ADMIN/OPERATOR only)

Note: Full anomaly detection requires backend implementation.
"""

import logging
import uuid
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Request, status, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/anomalies", tags=["anomalies"])

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
async def get_anomalies_health(request: Request):
    """
    Anomaly detection service health check.
    
    **Public access allowed**
    """
    trace_id = get_trace_id(request)
    
    return standard_response(
        message="Anomaly detection service is operational",
        data={
            "status": "ok",
            "service": "anomalies"
        },
        trace_id=trace_id
    )


@router.get("/recent")
async def get_recent_anomalies(
    request: Request,
    terminal: Optional[str] = Query(None, description="Terminal filter (optional)"),
    days: int = Query(7, description="Number of days to look back", ge=1, le=90),
    limit: int = Query(50, description="Maximum number of anomalies to return", ge=1, le=500)
):
    """
    Get recent anomalies.
    
    Returns detected anomalies (no-shows, unusual delays, pattern violations)
    for the specified time range.
    
    **Requires**: ADMIN or OPERATOR role
    
    **Note**: This endpoint requires backend anomaly detection service or NestJS endpoint.
    If not configured, returns a safe "not implemented" response.
    """
    require_operator_or_admin(request)
    trace_id = get_trace_id(request)
    auth_header = get_auth_header(request)
    
    # Try to query via NestJS backend anomalies endpoint
    try:
        from app.tools.nest_client import get_client, NEST_BASE_URL
        import httpx
        
        # Build query params
        params = {
            "days": days,
            "limit": limit
        }
        if terminal:
            params["terminal"] = terminal
        
        # Try to fetch from NestJS backend
        client = get_client()
        
        headers = {}
        if auth_header:
            headers["Authorization"] = auth_header
        headers["x-request-id"] = trace_id[:8]
        
        # Attempt to call /anomalies endpoint
        try:
            response = await client.get(
                f"{NEST_BASE_URL}/anomalies",
                params=params,
                headers=headers,
                timeout=5.0
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract anomalies from response
                if isinstance(data, dict):
                    anomalies = data.get("data") or data.get("anomalies") or []
                elif isinstance(data, list):
                    anomalies = data
                else:
                    anomalies = []
                
                return standard_response(
                    message=f"Found {len(anomalies)} recent anomalies",
                    data={
                        "anomalies": anomalies,
                        "terminal": terminal,
                        "days": days,
                        "count": len(anomalies)
                    },
                    trace_id=trace_id
                )
            
            elif response.status_code == 404 or response.status_code == 501:
                # Endpoint not implemented
                pass
            else:
                # Other error
                logger.warning(f"[{trace_id[:8]}] Anomalies endpoint returned {response.status_code}")
        
        except httpx.TimeoutException:
            logger.warning(f"[{trace_id[:8]}] Anomalies endpoint timeout")
        except httpx.HTTPError as e:
            logger.warning(f"[{trace_id[:8]}] Anomalies endpoint error: {type(e).__name__}")
    
    except ImportError:
        logger.warning(f"[{trace_id[:8]}] nest_client not available")
    except Exception as e:
        logger.exception(f"[{trace_id[:8]}] Anomalies query error: {e}")
    
    # Fallback: endpoint not available
    return standard_response(
        message="Anomaly detection feature not yet implemented",
        data={
            "status": "not_implemented",
            "reason": "Backend anomaly detection service not configured",
            "requested_params": {
                "terminal": terminal,
                "days": days,
                "limit": limit
            },
            "suggested_action": "Check back later or contact system administrator"
        },
        proofs={
            "trace_id": trace_id,
            "feature": "anomaly_detection",
            "status": "planned"
        },
        trace_id=trace_id
    )
