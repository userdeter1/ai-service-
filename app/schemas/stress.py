"""
Analytics/Stress Schemas

Pydantic models for analytics features:
- Stress index computation
- Proactive alerts
- What-if simulations

Matches AnalyticsAgent and analytics package (stress_index.py, proactive_alerts.py, what_if_simulation.py) outputs.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.base import Proofs


# ============================================================================
# Stress Index Schemas
# ============================================================================

class StressDrivers(BaseModel):
    """
    Stress index component drivers.
    
    Matches stress_index.compute_stress_index() drivers output.
    Each driver is 0-100 scale.
    """
    capacity_pressure: float = Field(..., description="Capacity utilization pressure (40% weight)", ge=0, le=100)
    traffic_pressure: float = Field(..., description="Traffic forecast pressure (30% weight)", ge=0, le=100)
    anomaly_pressure: float = Field(..., description="Anomaly incident pressure (20% weight)", ge=0, le=100)
    queue_pressure: float = Field(..., description="Booking queue pressure (10% weight)", ge=0, le=100)
    
    model_config = ConfigDict(extra="forbid")  # Strict - algorithm defines exact 4 drivers


class DataQualityInfo(BaseModel):
    """Data quality information."""
    mode: str = Field(..., description="Data quality mode (real/mvp/hybrid)")
    missing: List[str] = Field(default_factory=list, description="Missing data sources")
    sources: List[str] = Field(default_factory=list, description="Available data sources")
    
    model_config = ConfigDict(extra="allow")


class StressIndexResult(BaseModel):
    """
    Complete stress index result.
    
    Matches stress_index.compute_stress_index() output.
    """
    stress_index: float = Field(..., description="Composite stress index (0-100)", ge=0, le=100)
    level: str = Field(..., description="Stress level (low/medium/high/critical)")
    drivers: StressDrivers = Field(..., description="Stress component drivers")
    reasons: List[str] = Field(..., description="Human-readable stress reasons")
    recommendations: List[str] = Field(..., description="Actionable recommendations")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (terminal, gate, date, etc.)"
    )
    data_quality: Optional[DataQualityInfo] = Field(None, description="Data quality info")
    computed_at: str = Field(..., description="Computation timestamp (ISO format)")
    
    model_config = ConfigDict(extra="allow")


class StressIndexResponse(BaseModel):
    """
    Stress index agent response.
    
    Matches AnalyticsAgent._handle_stress_index() output.
    """
    message: str = Field(..., description="Stress index summary message")
    data: StressIndexResult = Field(..., description="Stress index result")
    proofs: Proofs = Field(..., description="Tracing and data sources")
    
    model_config = ConfigDict(extra="allow")


# ============================================================================
# Proactive Alerts Schemas
# ============================================================================

class AlertItem(BaseModel):
    """
    Single proactive alert.
    
    Matches proactive_alerts.generate_alerts() alert structure.
    """
    id: str = Field(..., description="Alert ID (ALERT-{uuid})")
    type: str = Field(
        ..., 
        description="Alert type (capacity/traffic/anomaly/stress/carrier_risk/no_show_risk)"
    )
    severity: str = Field(..., description="Severity level (low/medium/high/critical)")
    title: str = Field(..., description="Alert title")
    message: str = Field(..., description="Detailed alert message")
    recommended_actions: List[str] = Field(..., description="Recommended actions")
    evidence: Dict[str, Any] = Field(..., description="Supporting evidence/data")
    created_at: str = Field(..., description="Alert creation timestamp (ISO format)")
    
    model_config = ConfigDict(extra="allow")


class AlertsSummary(BaseModel):
    """Alert summary statistics."""
    by_type: Dict[str, int] = Field(default_factory=dict, description="Alert counts by type")
    by_severity: Dict[str, int] = Field(default_factory=dict, description="Alert counts by severity")
    
    model_config = ConfigDict(extra="allow")


class AlertsResponse(BaseModel):
    """
    Proactive alerts response.
    
    Matches AnalyticsAgent._handle_alerts() output.
    """
    message: str = Field(..., description="Alerts summary message")
    data: Dict[str, Any] = Field(
        ...,
        description="Alerts data (terminal, date, alerts_count, alerts list, summary)"
    )
    proofs: Proofs = Field(..., description="Tracing information")
    
    model_config = ConfigDict(extra="allow")


# ============================================================================
# What-If Simulation Schemas
# ============================================================================

class WhatIfScenario(BaseModel):
    """
    What-if scenario definition.
    
    Supported types:
    - shift_demand: Move X% bookings between terminals
    - gate_closure: Close gate for N hours
    - add_capacity: Add N slots
    - carrier_policy: Apply carrier prioritization
    """
    type: str = Field(
        ..., 
        description="Scenario type (shift_demand/gate_closure/add_capacity/carrier_policy)"
    )
    terminal: str = Field(..., description="Target terminal")
    date: str = Field(..., description="Target date (YYYY-MM-DD)")
    
    # shift_demand fields
    from_terminal: Optional[str] = Field(None, description="Source terminal for shift")
    to_terminal: Optional[str] = Field(None, description="Target terminal for shift")
    percentage: Optional[int] = Field(None, description="Percentage to shift (0-100)", ge=0, le=100)
    
    # gate_closure fields
    gate: Optional[str] = Field(None, description="Gate to close")
    duration_hours: Optional[int] = Field(None, description="Closure duration in hours", ge=0)
    
    # add_capacity fields
    additional_slots: Optional[int] = Field(None, description="Number of slots to add", ge=0)
    
    # carrier_policy fields
    policy: Optional[str] = Field(None, description="Policy type (deprioritize_low_tier/buffer_risky)")
    
    model_config = ConfigDict(extra="allow")


class ScenarioMetrics(BaseModel):
    """Scenario metrics (baseline or simulated)."""
    stress_index: float = Field(..., description="Stress index (0-100)", ge=0, le=100)
    stress_level: str = Field(..., description="Stress level (low/medium/high/critical)")
    alerts_count: int = Field(..., description="Number of alerts", ge=0)
    capacity_utilization: float = Field(..., description="Capacity utilization (0-1)", ge=0, le=1)
    
    model_config = ConfigDict(extra="allow")


class WhatIfResult(BaseModel):
    """
    What-if simulation result.
    
    Matches what_if_simulation.simulate_scenario() output.
    """
    scenario: WhatIfScenario = Field(..., description="Scenario definition")
    baseline: ScenarioMetrics = Field(..., description="Baseline metrics")
    simulated: ScenarioMetrics = Field(..., description="Simulated metrics")
    deltas: Dict[str, float] = Field(..., description="Metric deltas (simulated - baseline)")
    recommendations: List[str] = Field(..., description="Scenario recommendations")
    confidence: str = Field(..., description="Simulation confidence (high/medium/low)")
    data_quality: Optional[DataQualityInfo] = Field(None, description="Data quality info")
    simulated_at: str = Field(..., description="Simulation timestamp (ISO format)")
    
    model_config = ConfigDict(extra="allow")


class WhatIfResponse(BaseModel):
    """
    What-if simulation response.
    
    Matches AnalyticsAgent._handle_what_if() output.
    """
    message: str = Field(..., description="Simulation summary message")
    data: WhatIfResult = Field(..., description="Simulation result")
    proofs: Proofs = Field(..., description="Tracing and confidence info")
    
    model_config = ConfigDict(extra="allow")
