"""
Analytics API Router

REST API endpoints for analytics features:
- GET /analytics/stress-index: Compute stress/congestion index
- GET /analytics/alerts: Generate proactive operational alerts
- POST /analytics/what-if: Run what-if scenario simulations

All endpoints require ADMIN or OPERATOR role.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Query, Body, status
from pydantic import BaseModel, Field
from datetime import date

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class WhatIfScenarioRequest(BaseModel):
    """What-if scenario request model."""
    scenario: dict = Field(..., description="Scenario definition")
    terminal: str = Field(..., description="Terminal identifier")
    date: Optional[str] = Field(None, description="Target date (YYYY-MM-DD)")


# ============================================================================
# Analytics Endpoints
# ============================================================================

@router.get("/analytics/stress-index")
async def get_stress_index(
    terminal: str = Query(..., description="Terminal identifier (A, B, C, etc.)"),
    date: Optional[str] = Query(None, description="Target date (YYYY-MM-DD), defaults to today"),
    gate: Optional[str] = Query(None, description="Optional gate filter"),
    horizon_hours: int = Query(6, description="Forecast horizon in hours (default: 6)"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_user_role: Optional[str] = Header("ANON", alias="x-user-role"),
    x_request_id: Optional[str] = Header(None, alias="x-request-id")
):
    """
    Compute stress index for terminal/gate.
    
    Returns stress index (0-100) with explainable drivers:
    - Capacity pressure
    - Traffic pressure
    - Anomaly pressure
    - Queue pressure
    
    **RBAC**: Requires ADMIN or OPERATOR role.
    """
    # Check authorization
    if x_user_role not in ("ADMIN", "OPERATOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Analytics requires ADMIN or OPERATOR role (your role: {x_user_role})"
        )
    
    try:
        from app.analytics.stress_index import compute_stress_index
        
        result = await compute_stress_index(
            terminal=terminal,
            target_date=date or date.today().isoformat(),
            gate=gate,
            horizon_hours=horizon_hours,
            context={
                "auth_header": authorization,
                "trace_id": x_request_id or "api-direct"
            }
        )
        
        return {
            "status": "success",
            "data": result,
            "request_id": x_request_id
        }
    
    except Exception as e:
        logger.exception(f"Stress index computation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute stress index"
        )


@router.get("/analytics/alerts")
async def get_alerts(
    terminal: str = Query(..., description="Terminal identifier"),
    date: Optional[str] = Query(None, description="Target date (YYYY-MM-DD), defaults to today"),
    min_severity: str = Query("medium", description="Minimum alert severity (low, medium, high, critical)"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_user_role: Optional[str] = Header("ANON", alias="x-user-role"),
    x_request_id: Optional[str] = Header(None, alias="x-request-id")
):
    """
    Generate proactive operational alerts for terminal.
    
    Returns list of alerts with:
    - Type (capacity, traffic, anomaly, stress, carrier_risk, no_show_risk)
    - Severity (low, medium, high, critical)
    - Recommended actions
    - Evidence
    
    **RBAC**: Requires ADMIN or OPERATOR role.
    """
    # Check authorization
    if x_user_role not in ("ADMIN", "OPERATOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Analytics requires ADMIN or OPERATOR role (your role: {x_user_role})"
        )
    
    try:
        from app.analytics.proactive_alerts import generate_alerts
        
        alerts = await generate_alerts(
            terminal=terminal,
            target_date=date or date.today().isoformat(),
            context={
                "auth_header": authorization,
                "trace_id": x_request_id or "api-direct"
            },
            min_severity=min_severity
        )
        
        return {
            "status": "success",
            "data": {
                "terminal": terminal,
                "date": date or date.today().isoformat(),
                "alerts_count": len(alerts),
                "alerts": alerts
            },
            "request_id": x_request_id
        }
    
    except Exception as e:
        logger.exception(f"Alert generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate alerts"
        )


@router.post("/analytics/what-if")
async def simulate_what_if(
    request: WhatIfScenarioRequest = Body(...),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_user_role: Optional[str] = Header("ANON", alias="x-user-role"),
    x_request_id: Optional[str] = Header(None, alias="x-request-id")
):
    """
    Run what-if scenario simulation.
    
    Supported scenario types:
    - shift_demand: Move % of bookings between terminals
    - gate_closure: Close gate for N hours
    - add_capacity: Add N slots
    - carrier_policy: Apply carrier prioritization
    
    Returns baseline vs simulated metrics with recommendations.
    
    **RBAC**: Requires ADMIN or OPERATOR role.
    """
    # Check authorization
    if x_user_role not in ("ADMIN", "OPERATOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Analytics requires ADMIN or OPERATOR role (your role: {x_user_role})"
        )
    
    try:
        from app.analytics.what_if_simulation import simulate_scenario
        
        # Prepare scenario with terminal and date
        scenario = request.scenario
        scenario["terminal"] = request.terminal
        scenario["date"] = request.date or date.today().isoformat()
        
        result = await simulate_scenario(
            scenario=scenario,
            context={
                "auth_header": authorization,
                "trace_id": x_request_id or "api-direct"
            }
        )
        
        return {
            "status": "success",
            "data": result,
            "request_id": x_request_id
        }
    
    except Exception as e:
        logger.exception(f"What-if simulation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run simulation"
        )


@router.get("/analytics/health")
async def health_check():
    """Analytics service health check (public endpoint)."""
    return {
        "status": "healthy",
        "service": "analytics",
        "features": ["stress_index", "proactive_alerts", "what_if_simulation"]
    }
