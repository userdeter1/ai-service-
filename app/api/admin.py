"""
Admin API Endpoints

Administrative endpoints for system health, monitoring, and configuration.

Endpoints:
- GET /admin/health/models - Model registry health check
- GET /admin/health/services - Backend services health check
- GET /admin/system/info - System information

All endpoints require ADMIN role.
"""

import logging
import os
import uuid
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Request, status
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

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


def require_admin(request: Request) -> None:
    """Require ADMIN role, raise 403 if not."""
    role = get_role(request)
    if role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Admin access required (your role: {role})"
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

@router.get("/health/models")
async def get_models_health(request: Request):
    """
    Get health status of all loaded models.
    
    Returns model registry status including loaded models,
    available models, and configuration.
    
    **Requires**: ADMIN role
    """
    require_admin(request)
    trace_id = get_trace_id(request)
    
    try:
        from app.models.loader import models_health
        
        health = models_health()
        
        return standard_response(
            message=f"Model registry health: {len(health['loaded_models'])} models loaded",
            data=health,
            trace_id=trace_id
        )
        
    except Exception as e:
        logger.exception(f"[{trace_id[:8]}] Failed to get model health: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model health check failed"
        )


@router.get("/health/services")
async def get_services_health(request: Request):
    """
    Check health of backend services.
    
    Performs lightweight ping to each service base URL.
    Does not call specific endpoints to avoid side effects.
    
    **Requires**: ADMIN role
    """
    require_admin(request)
    trace_id = get_trace_id(request)
    
    services_status = {}
    
    # Service URLs
    from app.tools.booking_service_client import BOOKING_SERVICE_URL
    from app.tools.carrier_service_client import CARRIER_SERVICE_URL
    from app.tools.slot_service_client import SLOT_SERVICE_URL
    
    services = {
        "booking_service": BOOKING_SERVICE_URL,
        "carrier_service": CARRIER_SERVICE_URL,
        "slot_service": SLOT_SERVICE_URL,
    }
    
    # Ping each service
    async with httpx.AsyncClient(timeout=2.0) as client:
        for service_name, service_url in services.items():
            try:
                # Try to hit base URL or /health if exists
                response = await client.get(f"{service_url}/health", follow_redirects=False)
                
                services_status[service_name] = {
                    "url": service_url,
                    "status": "healthy" if response.status_code < 500 else "degraded",
                    "status_code": response.status_code,
                    "reachable": True
                }
            except httpx.TimeoutException:
                services_status[service_name] = {
                    "url": service_url,
                    "status": "timeout",
                    "reachable": False,
                    "error": "Request timeout"
                }
            except httpx.ConnectError:
                services_status[service_name] = {
                    "url": service_url,
                    "status": "unreachable",
                    "reachable": False,
                    "error": "Connection refused"
                }
            except Exception as e:
                services_status[service_name] = {
                    "url": service_url,
                    "status": "error",
                    "reachable": False,
                    "error": type(e).__name__
                }
    
    # Overall health
    all_healthy = all(
        svc.get("reachable") and svc.get("status") == "healthy"
        for svc in services_status.values()
    )
    
    overall = "healthy" if all_healthy else "degraded"
    
    return standard_response(
        message=f"Services health: {overall}",
        data={
            "overall": overall,
            "services": services_status
        },
        trace_id=trace_id
    )


@router.get("/system/info")
async def get_system_info(request: Request):
    """
    Get system information.
    
    Returns safe environment configuration and version information.
    Does not expose secrets or internal URLs.
    
    **Requires**: ADMIN role
    """
    require_admin(request)
    trace_id = get_trace_id(request)
    
    # Safe env vars only
    safe_config = {
        "model_mode_default": os.getenv("MODEL_MODE_DEFAULT", "real"),
        "model_artifacts_dir": os.getenv("MODEL_ARTIFACTS_DIR", "app/models/"),
        "enable_model_warmup": os.getenv("ENABLE_MODEL_WARMUP", "false"),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
    }
    
    # Version info
    try:
        from app.api import API_VERSION
    except ImportError:
        API_VERSION = "1.0.0"
    
    try:
        from app.orchestrator import __version__ as ORCHESTRATOR_VERSION
    except ImportError:
        ORCHESTRATOR_VERSION = "unknown"
    
    system_info = {
        "api_version": API_VERSION,
        "orchestrator_version": ORCHESTRATOR_VERSION,
        "config": safe_config,
        "python_version": os.sys.version.split()[0],
    }
    
    return standard_response(
        message="System information retrieved",
        data=system_info,
        trace_id=trace_id
    )
