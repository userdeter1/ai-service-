"""
Anomaly Detection Schemas

Pydantic models for anomaly detection.
Matches AnomalyAgent response structure.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.base import Proofs


class AnomalyItem(BaseModel):
    """
    Single anomaly event.
    
    Represents detected anomaly with metadata.
    """
    id: Optional[str] = Field(None, description="Anomaly ID")
    type: str = Field(..., description="Anomaly type (e.g., sensor, traffic, behavior)")
    severity: float = Field(..., description="Anomaly severity (0-1)", ge=0, le=1)
    description: str = Field(..., description="Anomaly description")
    timestamp: str = Field(..., description="Detection timestamp (ISO format)")
    terminal: Optional[str] = Field(None, description="Related terminal")
    gate: Optional[str] = Field(None, description="Related gate")
    booking_ref: Optional[str] = Field(None, description="Related booking reference")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional anomaly metadata")
    
    model_config = ConfigDict(extra="allow")


class AnomalySummary(BaseModel):
    """Anomaly summary statistics."""
    total_count: int = Field(..., description="Total anomaly count", ge=0)
    by_type: Dict[str, int] = Field(default_factory=dict, description="Counts by type")
    by_severity: Dict[str, int] = Field(default_factory=dict, description="Counts by severity level")
    avg_severity: float = Field(..., description="Average severity", ge=0, le=1)
    
    model_config = ConfigDict(extra="allow")


class AnomaliesResponse(BaseModel):
    """
    Anomaly detection response.
    
    Matches AnomalyAgent standard output structure.
    """
    message: str = Field(..., description="Anomaly detection summary message")
    data: Dict[str, Any] = Field(
        ...,
        description="Anomaly data (anomalies list, summary, time_window, etc.)"
    )
    proofs: Proofs = Field(..., description="Tracing and detection info")
    
    model_config = ConfigDict(extra="allow")
