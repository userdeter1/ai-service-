"""
Blockchain Audit Schemas

Pydantic models for blockchain audit features.
Matches BlockchainAuditAgent response structure.

Note: Current implementation may be placeholder, schemas support both:
- Real blockchain verification
- "Feature not enabled" placeholder responses
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.base import Proofs


class BlockchainAuditRequest(BaseModel):
    """
    Blockchain audit request.
    
    Requires at least one identifier (booking_ref or transaction_id).
    """
    booking_ref: Optional[str] = Field(None, description="Booking reference to audit")
    transaction_id: Optional[str] = Field(None, description="Transaction ID to audit")
    verify_only: bool = Field(
        default=True,
        description="Only verify (true) or also record (false)"
    )
    
    model_config = ConfigDict(extra="allow")


class BlockchainAuditResult(BaseModel):
    """
    Blockchain audit result.
    
    Supports both real verification and placeholder responses.
    """
    verified: bool = Field(..., description="Verification status")
    status: str = Field(..., description="Audit status (verified/not_found/not_enabled/error)")
    blockchain_hash: Optional[str] = Field(None, description="Blockchain transaction hash")
    block_number: Optional[int] = Field(None, description="Block number", ge=0)
    timestamp: Optional[str] = Field(None, description="Blockchain timestamp (ISO format)")
    chain: Optional[str] = Field(None, description="Blockchain network (mainnet/testnet/etc.)")
    reason: Optional[str] = Field(None, description="Verification reason/message")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional audit metadata")
    
    # Placeholder/not-enabled fields
    required_setup: Optional[Dict[str, Any]] = Field(
        None,
        description="Setup requirements if feature not enabled"
    )
    
    model_config = ConfigDict(extra="allow")


class BlockchainAuditResponse(BaseModel):
    """
    Blockchain audit agent response.
    
    Matches BlockchainAuditAgent standard output structure.
    Supports both real verification and "feature not enabled" responses.
    """
    message: str = Field(..., description="Audit result message")
    data: BlockchainAuditResult = Field(..., description="Audit result data")
    proofs: Proofs = Field(..., description="Tracing and verification info")
    
    model_config = ConfigDict(extra="allow")
