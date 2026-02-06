"""
Carrier Score Schemas

Pydantic models for carrier reliability scoring.
Matches CarrierScoreAgent response structure and carrier_scoring algorithm output.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.base import Proofs


class CarrierStatsSummary(BaseModel):
    """
    Carrier statistics summary from carrier_service_client.
    
    Matches normalize_carrier_stats() output.
    """
    total_bookings: int = Field(..., description="Total bookings in window", ge=0)
    completed_bookings: int = Field(..., description="Completed bookings", ge=0)
    cancelled_bookings: int = Field(..., description="Cancelled bookings", ge=0)
    no_shows: int = Field(..., description="No-show incidents", ge=0)
    late_arrivals: int = Field(..., description="Late arrival count", ge=0)
    avg_delay_minutes: float = Field(..., description="Average delay in minutes", ge=0)
    avg_dwell_minutes: float = Field(..., description="Average dwell time in minutes", ge=0)
    anomaly_count: int = Field(..., description="Anomaly/incident count", ge=0)
    last_activity_at: Optional[str] = Field(None, description="Last activity timestamp")
    
    model_config = ConfigDict(extra="allow")


class CarrierScoreComponents(BaseModel):
    """
    Carrier score components from carrier_scoring algorithm.
    
    Breakdown of weighted components:
    - completion_score: Based on completion rate (weight 30%)
    - timeliness_score: Based on on-time performance (weight 25%)
    - reliability_score: Based on no-show rate (weight 25%)
    - compliance_score: Based on anomaly rate (weight 20%)
    """
    completion_score: float = Field(..., description="Completion rate score (0-100)")
    timeliness_score: float = Field(..., description="On-time performance score (0-100)")
    reliability_score: float = Field(..., description="No-show reliability score (0-100)")
    compliance_score: float = Field(..., description="Compliance/anomaly score (0-100)")
    
    model_config = ConfigDict(extra="forbid")  # Strict - algorithm defines exact fields


class DataQuality(BaseModel):
    """Data quality indicator for MVP fallback."""
    missing_metrics: Optional[List[str]] = Field(None, description="Missing data metrics")
    source: Optional[str] = Field(None, description="Data source identifier")
    note: Optional[str] = Field(None, description="Data quality note")
    
    model_config = ConfigDict(extra="allow")


class CarrierScoreResult(BaseModel):
    """
    Complete carrier score result.
    
    Matches score_carrier() algorithm output from carrier_scoring.py.
    Also matches CarrierScoreAgent data payload.
    """
    carrier_id: str = Field(..., description="Carrier identifier")
    score: float = Field(..., description="Overall reliability score (0-100)", ge=0, le=100)
    tier: str = Field(..., description="Tier classification (A/B/C/D)")
    confidence: float = Field(..., description="Score confidence (0-1)", ge=0, le=1)
    stats: CarrierStatsSummary = Field(..., description="Carrier statistics summary")
    components: CarrierScoreComponents = Field(..., description="Score component breakdown")
    reasons: List[str] = Field(..., description="Human-readable score reasons")
    data_quality: Optional[DataQuality] = Field(None, description="Data quality (if MVP fallback)")
    
    model_config = ConfigDict(extra="allow")


class CarrierScoreResponse(BaseModel):
    """
    Standard carrier score agent response.
    
    Matches CarrierScoreAgent._build_success_response() output.
    """
    message: str = Field(..., description="User-facing score message with insights")
    data: CarrierScoreResult = Field(..., description="Carrier score result")
    proofs: Proofs = Field(..., description="Tracing, sources, algorithm info")
    
    model_config = ConfigDict(extra="allow")
