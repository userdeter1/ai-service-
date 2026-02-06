"""
Booking Agent - Handles booking status queries

Responsibilities:
- Extract and validate booking references from user queries
- Query real booking service backend for status information
- Return structured booking status information
- Support single and multiple booking references
- Provide clear validation and error messages

IMPORTANT: Does NOT handle persistence (NestJS backend handles that via chat.py)
"""

import logging
from typing import Dict, Any, List, Optional, Union
from fastapi import HTTPException

from app.agents.base_agent import BaseAgent
# Use absolute import to be robust regardless of app/tools/__init__.py
from app.tools.booking_service_client import (
    get_booking_status,
    get_bookings_batch,
    BOOKING_SERVICE_URL,
    BOOKING_STATUS_PATH,
    BOOKING_BATCH_STATUS_PATH
)

logger = logging.getLogger(__name__)


class BookingAgent(BaseAgent):
    """
    Agent specialized in handling booking status queries.
    
    Inherits from BaseAgent which provides:
    - async execute() method (called by orchestrator)
    - run() method (implemented here)
    - Helper methods for response formatting
    """

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Core business logic for booking status queries.
        
        Args:
            context: Full context dictionary from orchestrator containing:
                - message: User's query
                - entities: Extracted entities (including booking_ref)
                - history: Normalized conversation history
                - user_role: User role (ADMIN/OPERATOR/CARRIER)
                - user_id: User identifier
                - trace_id: Request trace ID
                - auth_header: Authorization header (required)
        
        Returns:
            Structured response with message, data, and proofs
        """
        # Extract context using BaseAgent helpers
        trace_id = self.get_trace_id(context)
        entities = self.get_entities(context)
        user_role = self.get_user_role(context)
        auth_header = self.get_auth_header(context)
        
        # Extract and validate booking reference(s)
        booking_refs = self._extract_booking_refs(entities)
        
        if not booking_refs:
            return self.validation_error(
                message="I couldn't find a booking reference in your message. Please provide a booking reference.",
                suggestion="Try asking: 'What's the status of REF12345?' or 'Check booking REF789'",
                missing_field="booking_ref",
                example="REF12345",
                trace_id=trace_id
            )
        
        # Validate auth header
        if not auth_header:
            return self.error_response(
                message="Authentication required to check booking status. Please ensure you're logged in.",
                trace_id=trace_id,
                error_type="Unauthorized"
            )
        
        # Log minimal info (privacy: no full message)
        ref_count = len(booking_refs) if isinstance(booking_refs, list) else 1
        logger.info(f"[{trace_id[:8]}] BookingAgent processing {ref_count} ref(s)")
        
        # Extract optional entities
        terminal = entities.get("terminal")
        gate = entities.get("gate")
        
        # Query booking service (handles single or multiple refs)
        try:
            if isinstance(booking_refs, list):
                return await self._handle_multiple_bookings(
                    booking_refs, auth_header, terminal, gate, trace_id, user_role
                )
            else:
                return await self._handle_single_booking(
                    booking_refs, auth_header, terminal, gate, trace_id, user_role
                )
        except HTTPException as e:
            # Convert HTTP exceptions to user-friendly messages
            return self._handle_service_error(e, booking_refs, trace_id)
        except Exception as e:
            # Unexpected errors
            logger.exception(f"[{trace_id[:8]}] Unexpected error in BookingAgent: {e}")
            return self.error_response(
                message="I encountered an unexpected error while checking booking status. Please try again.",
                trace_id=trace_id,
                error_type=type(e).__name__
            )

    def _extract_booking_refs(self, entities: Dict[str, Any]) -> Optional[Union[str, List[str]]]:
        """
        Extract booking reference(s) from entities.
        
        Args:
            entities: Extracted entities dict from orchestrator
        
        Returns:
            Single booking ref (str), list of refs, or None
        """
        booking_ref = entities.get("booking_ref")
        
        if not booking_ref:
            return None
        
        # Handle both single string and list
        if isinstance(booking_ref, list):
            # Filter out empty strings and normalize
            refs = [ref.strip().upper() for ref in booking_ref if ref and ref.strip()]
            return refs if refs else None
        elif isinstance(booking_ref, str):
            ref = booking_ref.strip().upper()
            return ref if ref else None
        
        return None

    async def _handle_single_booking(
        self,
        booking_ref: str,
        auth_header: str,
        terminal: Optional[str],
        gate: Optional[str],
        trace_id: str,
        user_role: str
    ) -> Dict[str, Any]:
        """
        Handle single booking reference query.
        Calls real booking service API.
        
        Args:
            booking_ref: Booking reference to query
            auth_header: Authorization header
            terminal: Optional terminal filter
            gate: Optional gate filter
            trace_id: Request trace ID
            user_role: User role
        
        Returns:
            Structured response with booking data
        """
        # Call real booking service
        booking_data = await get_booking_status(
            booking_ref=booking_ref,
            auth_header=auth_header,
            request_id=trace_id[:8]
        )
        
        # Build user-facing message
        message = (
            f"Booking {booking_data['booking_ref']} is currently {booking_data['status']}.\n"
            f"Terminal: {booking_data['terminal']}\n"
            f"Gate: {booking_data['gate']}\n"
            f"Slot Time: {booking_data['slot_time']}\n"
            f"Last Update: {booking_data['last_update']}"
        )
        
        # Build structured response
        return {
            "message": message,
            "data": {
                "booking_ref": booking_data["booking_ref"],
                "status": booking_data["status"],
                "terminal": booking_data["terminal"],
                "gate": booking_data["gate"],
                "slot_time": booking_data["slot_time"],
                "last_update": booking_data["last_update"]
            },
            "proofs": {
                "trace_id": trace_id,
                "sources": [
                    {
                        "type": "booking_service",
                        "service": BOOKING_SERVICE_URL,
                        "endpoint": BOOKING_STATUS_PATH.format(
                            booking_ref=booking_ref
                        )
                    }
                ],
                "request_id": trace_id[:8],
                "user_role": user_role
            }
        }

    async def _handle_multiple_bookings(
        self,
        booking_refs: List[str],
        auth_header: str,
        terminal: Optional[str],
        gate: Optional[str],
        trace_id: str,
        user_role: str
    ) -> Dict[str, Any]:
        """
        Handle multiple booking references query.
        Calls real booking service batch API.
        
        Args:
            booking_refs: List of booking references to query
            auth_header: Authorization header
            terminal: Optional terminal filter
            gate: Optional gate filter
            trace_id: Request trace ID
            user_role: User role
        
        Returns:
            Structured response with multiple booking data
        """
        # Call real booking service batch endpoint
        bookings_data = await get_bookings_batch(
            booking_refs=booking_refs,
            auth_header=auth_header,
            request_id=trace_id[:8]
        )
        
        # Build user-facing message
        message_parts = [f"Found {len(bookings_data)} booking(s):\n"]
        
        for booking in bookings_data:
            message_parts.append(
                f"• {booking['booking_ref']}: {booking['status']} "
                f"(Terminal {booking['terminal']}, Gate {booking['gate']}, {booking['slot_time']})"
            )
        
        message = "\n".join(message_parts)
        
        # Build structured response
        return {
            "message": message,
            "data": {
                "booking_refs": booking_refs,
                "bookings": [
                    {
                        "booking_ref": b["booking_ref"],
                        "status": b["status"],
                        "terminal": b["terminal"],
                        "gate": b["gate"],
                        "slot_time": b["slot_time"],
                        "last_update": b["last_update"]
                    }
                    for b in bookings_data
                ],
                "count": len(bookings_data)
            },
            "proofs": {
                "trace_id": trace_id,
                "sources": [
                    {
                        "type": "booking_service",
                        "service": BOOKING_SERVICE_URL,
                        "endpoint": BOOKING_BATCH_STATUS_PATH
                    }
                ],
                "request_id": trace_id[:8],
                "user_role": user_role
            }
        }

    def _handle_service_error(
        self,
        http_exception: HTTPException,
        booking_refs: Union[str, List[str]],
        trace_id: str
    ) -> Dict[str, Any]:
        """
        Convert HTTP exceptions from booking service to user-friendly messages.
        
        Args:
            http_exception: HTTPException from booking service
            booking_refs: Booking reference(s) that were queried
            trace_id: Request trace ID
        
        Returns:
            User-friendly error response
        """
        status_code = http_exception.status_code
        
        # Map HTTP status codes to user-friendly messages
        if status_code == 401:
            message = "Your session has expired. Please log in again to check booking status."
            error_type = "Unauthorized"
        elif status_code == 403:
            message = "You don't have permission to access this booking information."
            error_type = "Forbidden"
        elif status_code == 404:
            if isinstance(booking_refs, list):
                refs_str = ", ".join(booking_refs)
                message = f"One or more bookings not found: {refs_str}. Please check the booking references."
            else:
                message = f"Booking {booking_refs} not found. Please check the booking reference."
            error_type = "NotFound"
        elif status_code == 503:
            message = "The booking service is temporarily unavailable. Please try again in a moment."
            error_type = "ServiceUnavailable"
        else:
            message = "I couldn't retrieve booking information at this time. Please try again later."
            error_type = "ServiceError"
        
        logger.warning(f"[{trace_id[:8]}] Booking service error {status_code}: {http_exception.detail}")
        
        return self.error_response(
            message=message,
            trace_id=trace_id,
            error_type=error_type,
            status_code=status_code
        )


# ============================================================================
# Expected Runtime Behavior Examples
# ============================================================================
#
# EXAMPLE 1: Single booking query
# User: "status REF123"
# Context: { "entities": {"booking_ref": "REF123"}, "auth_header": "Bearer ..." }
# Result:
# {
#   "message": "Booking REF123 is currently Confirmed.\nTerminal: A\nGate: G2\n...",
#   "data": {"booking_ref": "REF123", "status": "Confirmed", ...},
#   "proofs": {...}
# }
#
# EXAMPLE 2: Multiple booking query
# User: "check REF123 and REF999"
# Context: { "entities": {"booking_ref": ["REF123", "REF999"]}, "auth_header": "Bearer ..." }
# Result:
# {
#   "message": "Found 2 booking(s):\n• REF123: Confirmed ...\n• REF999: Pending ...",
#   "data": {"booking_refs": ["REF123", "REF999"], "bookings": [...], "count": 2},
#   "proofs": {...}
# }
#
# EXAMPLE 3: Missing auth header
# User: "status REF123"
# Context: { "entities": {"booking_ref": "REF123"}, "auth_header": None }
# Result:
# {
#   "message": "Authentication required to check booking status. Please ensure you're logged in.",
#   "data": {"error": "execution_failed", "error_type": "Unauthorized"},
#   "proofs": {"trace_id": "...", "status": "failed"}
# }
#
# EXAMPLE 4: Booking not found (404 from service)
# User: "status REF999"
# Context: { "entities": {"booking_ref": "REF999"}, "auth_header": "Bearer ..." }
# Service returns: HTTPException(404)
# Result:
# {
#   "message": "Booking REF999 not found. Please check the booking reference.",
#   "data": {"error": "execution_failed", "error_type": "NotFound", "status_code": 404},
#   "proofs": {"trace_id": "...", "status": "failed"}
# }
#
# ============================================================================
