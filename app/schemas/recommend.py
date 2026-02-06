"""
Recommendation Schemas

Pydantic models for slot availability and recommendations.
Matches SlotAgent responses and slot_service_client normalize_slot() structure.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.base import Proofs


class SlotItem(BaseModel):
    """
    Single slot item.
    
    Matches slot_service_client._normalize_slot() output.
    Required fields from service:
    - slot_id, start, end, capacity, remaining, terminal, gate
    
    Optional fields added by slot_recommender:
    - rank_score: Recommendation score
    - rank_reasons: Why this slot was recommended
    """
    slot_id: str = Field(..., description="Unique slot identifier")
    start: str = Field(..., description="Slot start time (ISO format)")
    end: str = Field(..., description="Slot end time (ISO format)")
    capacity: int = Field(..., description="Total slot capacity", ge=0)
    remaining: int = Field(..., description="Remaining capacity", ge=0)
    terminal: str = Field(..., description="Terminal identifier (A, B, C, etc.)")
    gate: str = Field(..., description="Gate identifier")
    rank_score: Optional[float] = Field(None, description="Recommendation score (0-100)")
    rank_reasons: Optional[List[str]] = Field(None, description="Recommendation reasons")
    
    model_config = ConfigDict(extra="allow")


class SlotRecommendationResult(BaseModel):
    """
    Slot recommendation result from slot_recommender algorithm.
    
    Matches SlotAgent recommendation response data.
    """
    terminal: str = Field(..., description="Terminal identifier")
    date: str = Field(..., description="Target date (YYYY-MM-DD)")
    recommended: List[SlotItem] = Field(..., description="Recommended slots (ranked)")
    strategy: str = Field(..., description="Recommendation strategy used")
    reasons: List[str] = Field(..., description="Overall recommendation reasons")
    total_candidates: int = Field(..., description="Total slots considered", ge=0)
    carrier_score: Optional[float] = Field(None, description="Carrier reliability score if used")
    
    model_config = ConfigDict(extra="allow")


class SlotAvailabilityResponse(BaseModel):
    """
    Slot availability response (no recommendations).
    
    Simple list of available slots with stats.
    """
    message: str = Field(..., description="Availability summary message")
    data: Dict[str, Any] = Field(
        ...,
        description="Availability data (slots list, terminal, date, stats)"
    )
    proofs: Proofs = Field(..., description="Tracing information")
    
    model_config = ConfigDict(extra="allow")


class SlotRecommendationResponse(BaseModel):
    """
    Slot recommendation response from SlotAgent.
    
    Includes ranked recommendations with reasons.
    """
    message: str = Field(..., description="Recommendation summary message")
    data: SlotRecommendationResult = Field(..., description="Recommendation result with ranked slots")
    proofs: Proofs = Field(..., description="Tracing, sources, algorithm info")
    
    model_config = ConfigDict(extra="allow")
