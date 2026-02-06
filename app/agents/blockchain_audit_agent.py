"""
Blockchain Audit Agent - Handles blockchain audit trail queries

Responsibilities:
- Audit trail verification
- Integrity checks for bookings and transactions
- Blockchain proof of execution

Uses REAL->MVP fallback strategy:
- REAL: Calls blockchain audit service if available
- MVP: Returns "feature not enabled" with clear explanation
"""

import logging
from typing import Dict, Any, Optional

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class BlockchainAuditAgent(BaseAgent):
    """
    Agent specialized in handling blockchain audit and integrity verification queries.
    
    Intent mapping: blockchain_audit -> BlockchainAuditAgent
    
    NOTE: This is a placeholder for future blockchain integration.
    Returns honest "not enabled" responses until backend is configured.
    """

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Core business logic for blockchain audit queries.
        
        Args:
            context: Full context dictionary from orchestrator
        
        Returns:
            Structured response with message, data, and proofs
        """
        trace_id = self.get_trace_id(context)
        entities = self.get_entities(context)
        auth_header = self.get_auth_header(context)
        user_role = self.get_user_role(context)
        
        # Require authentication
        if not auth_header:
            return self.error_response(
                message="Authentication required to access blockchain audit features.",
                trace_id=trace_id,
                error_type="Unauthorized"
            )
        
        # Check role authorization (ADMIN/OPERATOR only)
        if user_role not in ("ADMIN", "OPERATOR"):
            return self.error_response(
                message=f"Access denied. Blockchain audit requires ADMIN or OPERATOR role (your role: {user_role}).",
                trace_id=trace_id,
                error_type="Forbidden"
            )
        
        # Extract entities
        booking_ref = entities.get("booking_ref")
        transaction_id = entities.get("transaction_id")
        
        # Validate input - need at least one identifier
        if not booking_ref and not transaction_id:
            return self.validation_error(
                message="Please provide a booking reference or transaction ID to verify.",
                suggestion="Try: 'Verify blockchain for REF123' or 'Check audit trail for transaction TX456'",
                missing_field="booking_ref or transaction_id",
                example="booking_ref=REF123",
                trace_id=trace_id
            )
        
        # REAL Mode: Try blockchain tool/service
        try:
            from app.tools.blockchain_tool import verify_blockchain_integrity
            from fastapi import HTTPException
            
            # Call blockchain verification
            result = await verify_blockchain_integrity(
                booking_ref=booking_ref,
                transaction_id=transaction_id,
                auth_header=auth_header,
                trace_id=trace_id
            )
            
            # Format message based on verification result
            message = self._format_audit_message(result, booking_ref or transaction_id)
            
            # Build comprehensive proofs
            proofs = {
                "trace_id": trace_id,
                "request_id": trace_id[:8],
                "user_role": user_role,
                "sources": ["blockchain_service"],
                "verified": result.get("verified", False)
            }
            
            # Add blockchain metadata to proofs
            chain_info = result.get("chain", {})
            if chain_info:
                proofs["blockchain"] = {
                    "mode": chain_info.get("mode"),
                    "chain_id": chain_info.get("chain_id"),
                    "contract": chain_info.get("contract"),
                    "tx_hash": chain_info.get("tx_hash"),
                    "block": chain_info.get("block")
                }
            
            return {
                "message": message,
                "data": result,
                "proofs": proofs
            }
        
        except HTTPException as e:
            # Check if endpoint missing (404/405/501)
            from app.tools.blockchain_service_client import is_endpoint_missing
            
            if is_endpoint_missing(e):
                logger.info(f"[{trace_id[:8]}] Blockchain service not implemented")
                return self._feature_not_enabled_response(trace_id, booking_ref, transaction_id)
            
            # Other HTTP errors (auth, connection, etc.)
            return self.error_response(
                message=f"Blockchain verification failed: {e.detail}",
                trace_id=trace_id,
                error_type=type(e).__name__,
                status_code=e.status_code
            )
        
        except ImportError as e:
            logger.warning(f"[{trace_id[:8]}] Blockchain tool not available: {e}")
            return self._feature_not_enabled_response(trace_id, booking_ref, transaction_id)
        
        except Exception as e:
            logger.exception(f"[{trace_id[:8]}] Blockchain verification error: {e}")
            return self.error_response(
                message="Failed to verify blockchain audit trail. Please try again.",
                trace_id=trace_id,
                error_type=type(e).__name__
            )
    
    def _format_audit_message(
        self,
        data: Dict[str, Any],
        booking_ref: Optional[str]
    ) -> str:
        """Format blockchain audit data into user-friendly message."""
        verified = data.get("verified", False)
        hash_value = data.get("hash", "")
        timestamp = data.get("timestamp", "")
        
        ref = booking_ref or "transaction"
        
        if verified:
            message = f"✓ Blockchain verification successful for {ref}"
            if hash_value:
                message += f"\n• Hash: {hash_value[:16]}..."
            if timestamp:
                message += f"\n• Timestamp: {timestamp}"
        else:
            message = f"⚠️ Blockchain verification failed for {ref}"
            reason = data.get("reason", "Unknown")
            message += f"\n• Reason: {reason}"
        
        return message
    
    def _feature_not_enabled_response(
        self,
        trace_id: str,
        booking_ref: Optional[str],
        transaction_id: Optional[str]
    ) -> Dict[str, Any]:
        """Return response when blockchain feature not enabled."""
        message = "Blockchain audit feature is not yet enabled."
        
        required_setup = [
            "Blockchain node integration",
            "Smart contract deployment for audit trail",
            "Backend endpoint: POST /blockchain/audit",
            "Blockchain verification service"
        ]
        
        data = {
            "status": "not_enabled",
            "reason": "Blockchain integration not configured",
            "requested_params": {
                "booking_ref": booking_ref,
                "transaction_id": transaction_id
            },
            "required_setup": required_setup,
            "suggested_action": "Contact system administrator to enable blockchain audit trail"
        }
        
        return {
            "message": message,
            "data": data,
            "proofs": {
                "trace_id": trace_id,
                "feature": "blockchain_audit",
                "status": "planned"
            }
        }
