"""
Base Schemas

Core Pydantic models used across all agent responses.
Matches BaseAgent.success_response() / error_response() / validation_error() structure.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class Proofs(BaseModel):
    """
    Proof/tracing information included in all agent responses.
    
    Standard fields from BaseAgent:
    - trace_id: Request trace ID
    - request_id: Optional short request ID
    - user_role: User's role (ADMIN/OPERATOR/CARRIER)
    - sources: List of data sources used (service clients, APIs, models)
    - status: Execution status (success/failed/fallback)
    - algorithm: Algorithm identifier (e.g., "deterministic_weighted_scoring")
    - mode: Data quality mode (real/mvp/hybrid)
    - is_fallback: Whether MVP fallback was used
    - latency_ms: Optional response time
    """
    trace_id: Optional[str] = Field(None, description="Request trace ID")
    request_id: Optional[str] = Field(None, description="Short request ID")
    user_role: Optional[str] = Field(None, description="User role (ADMIN/OPERATOR/CARRIER)")
    sources: Optional[List[Any]] = Field(None, description="Data sources (list of dicts or strings)")
    status: Optional[str] = Field(None, description="Execution status")
    algorithm: Optional[str] = Field(None, description="Algorithm identifier")
    mode: Optional[str] = Field(None, description="Data quality mode (real/mvp/hybrid)")
    is_fallback: Optional[bool] = Field(None, description="Whether MVP fallback was used")
    latency_ms: Optional[float] = Field(None, description="Response time in milliseconds")
    validation: Optional[str] = Field(None, description="Validation status (for validation errors)")
    reason: Optional[str] = Field(None, description="Reason for status (for errors)")
    
    model_config = ConfigDict(extra="allow")  # Allow extra fields for forward compatibility


class AgentResponse(BaseModel):
    """
    Standard agent response structure.
    Matches BaseAgent.success_response() output.
    
    All agents return:
    - message: User-facing message
    - data: Typed payload (varies by agent)
    - proofs: Tracing and source information
    """
    message: str = Field(..., description="User-facing response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data payload")
    proofs: Optional[Proofs] = Field(None, description="Proof/tracing information")
    
    model_config = ConfigDict(extra="allow")


class ErrorResponse(BaseModel):
    """
    Standard error response structure.
    Matches BaseAgent.error_response() output.
    
    Returns:
    - message: User-facing error message
    - data: Error details with 'error' and 'error_type' keys
    - proofs: Tracing information with 'status': 'failed'
    """
    message: str = Field(..., description="User-facing error message")
    data: Dict[str, Any] = Field(..., description="Error details")
    proofs: Optional[Proofs] = Field(None, description="Proof/tracing with status=failed")
    
    model_config = ConfigDict(extra="allow")


class ValidationErrorResponse(BaseModel):
    """
    Validation error response structure.
    Matches BaseAgent.validation_error() output.
    
    Includes:
    - message: Error message with suggestion
    - data: Error details with suggestion, missing_field, example
    - proofs: Tracing with validation='failed'
    """
    message: str = Field(..., description="Validation error message with suggestion")
    data: Dict[str, Any] = Field(
        ..., 
        description="Error details (error, suggestion, missing_field, example)"
    )
    proofs: Optional[Proofs] = Field(None, description="Proof with validation=failed")
    
    model_config = ConfigDict(extra="allow")
