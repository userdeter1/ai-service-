"""
Traffic Schemas

Pydantic models for traffic forecasting.
Matches TrafficAgent response structure (flexible to accommodate various traffic data).
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.base import Proofs


class TrafficForecastItem(BaseModel):
    """Single traffic forecast data point."""
    hour: str = Field(..., description="Hour timestamp (ISO format or HH:MM)")
    intensity: float = Field(..., description="Traffic intensity (0-1)", ge=0, le=1)
    vehicle_count: Optional[int] = Field(None, description="Estimated vehicle count", ge=0)
    congestion_level: Optional[str] = Field(None, description="Congestion level (low/medium/high)")
    
    model_config = ConfigDict(extra="allow")


class TrafficForecastResult(BaseModel):
    """
    Traffic forecast result.
    
    Flexible structure to accommodate various traffic forecasting outputs.
    """
    terminal: Optional[str] = Field(None, description="Terminal identifier")
    date: Optional[str] = Field(None, description="Forecast date (YYYY-MM-DD)")
    intensity: Optional[float] = Field(None, description="Overall intensity (0-1)", ge=0, le=1)
    peak_hour: Optional[str] = Field(None, description="Peak traffic hour")
    peak_intensity: Optional[float] = Field(None, description="Peak intensity value", ge=0, le=1)
    forecasts: List[TrafficForecastItem] = Field(
        default_factory=list,
        description="Hourly traffic forecasts"
    )
    data_quality: Optional[str] = Field(None, description="Data quality mode (real/mvp)")
    
    model_config = ConfigDict(extra="allow")  # Flexible for various traffic data structures


class TrafficResponse(BaseModel):
    """
    Traffic forecast agent response.
    
    Matches TrafficAgent standard output structure.
    """
    message: str = Field(..., description="Traffic forecast summary message")
    data: TrafficForecastResult = Field(..., description="Traffic forecast data")
    proofs: Proofs = Field(..., description="Tracing and sources")
    
    model_config = ConfigDict(extra="allow")
