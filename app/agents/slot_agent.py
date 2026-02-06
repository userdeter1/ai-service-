"""
Slot Agent - Handles slot availability and recommendations

Responsibilities:
- Query real slot availability endpoints
- Recommend optimal slots using algorithm
- Fallback gracefully when endpoints missing
- Provide actionable slot recommendations

Fallback strategy:
- If slot availability endpoint missing -> return helpful error
- Always try to provide recommendations when data exists
"""

import re
import logging
from typing import Dict, Any, Optional, List
from datetime import date, timedelta
from fastapi import HTTPException

from app.agents.base_agent import BaseAgent
from app.tools.slot_service_client import (
    get_availability,
    is_endpoint_missing,
    SLOT_SERVICE_URL,
    SLOT_AVAILABILITY_PATH
)
from app.algorithms.slot_recommender import recommend_slots

logger = logging.getLogger(__name__)


class SlotAgent(BaseAgent):
    """Agent specialized in slot availability queries and recommendations."""

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Core logic for slot availability and recommendations.
        
        Strategy:
        1. Extract terminal/date from context/entities/message
        2. Try REAL get_availability() endpoint
        3. If missing -> return helpful error with missing endpoint info
        4. If user wants recommendations OR low availability -> run recommender
        """
        trace_id = self.get_trace_id(context)
        entities = self.get_entities(context)
        auth_header = self.get_auth_header(context)
        message = self.get_message(context)
        user_role = self.get_user_role(context)
        
        # Extract parameters
        terminal = self._extract_terminal(entities, message)
        date_str = self._extract_date(entities, message)
        gate = entities.get("gate")
        
        # Validation
        if not terminal:
            return self.validation_error(
                message="Please specify which terminal you're interested in.",
                suggestion="Try asking: 'Show slots for terminal A' or 'Availability at terminal B tomorrow'",
                missing_field="terminal",
                example="terminal A",
                trace_id=trace_id
            )
        
        # Auth check - if no auth header, return error for real protected endpoints
        if not auth_header:
            return self.error_response(
                message="Authentication required to check slot availability. Please log in.",
                trace_id=trace_id,
                error_type="Unauthorized"
            )
        
        logger.info(f"[{trace_id[:8]}] SlotAgent processing terminal {terminal}, date {date_str}")
        
        # Check if user wants recommendations
        wants_recommendations = self._wants_recommendations(message)
        
        # Try REAL endpoint
        try:
            slots = await get_availability(
                terminal=terminal,
                date=date_str,
                gate=gate,
                auth_header=auth_header,
                request_id=trace_id[:8]
            )
            
            # Check if we should recommend
            should_recommend = (
                wants_recommendations or
                self._has_low_availability(slots)
            )
            
            if should_recommend:
                return await self._build_recommendation_response(
                    slots=slots,
                    terminal=terminal,
                    date_str=date_str,
                    gate=gate,
                    context=context,
                    trace_id=trace_id,
                    user_role=user_role
                )
            else:
                return self._build_availability_response(
                    slots=slots,
                    terminal=terminal,
                    date_str=date_str,
                    trace_id=trace_id,
                    user_role=user_role
                )
            
        except HTTPException as e:
            if is_endpoint_missing(e):
                logger.warning(f"[{trace_id[:8]}] Slot availability endpoint not available")
                return self._return_missing_backend_error(terminal, date_str, trace_id)
            
            return self._handle_slot_service_error(e, terminal, trace_id)
            
        except Exception as e:
            logger.exception(f"[{trace_id[:8]}] Unexpected error in SlotAgent: {e}")
            return self.error_response(
                message="I encountered an unexpected error while checking slot availability. Please try again.",
                trace_id=trace_id,
                error_type=type(e).__name__
            )

    def _extract_terminal(self, entities: Dict[str, Any], message: str) -> Optional[str]:
        """Extract terminal from entities or parse from message."""
        # Check entities
        terminal = entities.get("terminal")
        if terminal:
            return str(terminal).upper()
        
        # Parse from message: "terminal A", "terminale B", etc.
        patterns = [
            r"\btermin[ae]l?\s+([A-Z])\b",
            r"\b([A-Z])\s+terminal\b",
            r"\bterminal\s*:\s*([A-Z])\b"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        
        return None

    def _extract_date(self, entities: Dict[str, Any], message: str) -> str:
        """
        Extract date from entities or message, default to today.
        
        Supports:
        - entities["date_today"], ["date_tomorrow"], ["date_yesterday"]
        - Explicit YYYY-MM-DD in message
        - Default: today
        """
        # Check entities
        if entities.get("date_today"):
            return date.today().isoformat()
        elif entities.get("date_tomorrow"):
            return (date.today() + timedelta(days=1)).isoformat()
        elif entities.get("date_yesterday"):
            # FIX: Subtract 1 day, not add
            return (date.today() - timedelta(days=1)).isoformat()
        
        # Parse explicit date from message
        date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", message)
        if date_match:
            return date_match.group(1)
        
        # Default: today
        return date.today().isoformat()

    def _wants_recommendations(self, message: str) -> bool:
        """Check if user is asking for recommendations."""
        keywords = [
            "recommend", "suggest", "alternative", "better", "best",
            "other options", "what else", "alternatives"
        ]
        message_lower = message.lower()
        return any(kw in message_lower for kw in keywords)

    def _has_low_availability(self, slots: List[Dict[str, Any]]) -> bool:
        """Check if slots have low overall availability."""
        if not slots:
            return False
        
        total_remaining = sum(s.get("remaining", 0) for s in slots)
        total_capacity = sum(s.get("capacity", 1) for s in slots)
        
        if total_capacity == 0:
            return False
        
        availability_ratio = total_remaining / total_capacity
        return availability_ratio < 0.3  # Less than 30% available

    async def _build_recommendation_response(
        self,
        slots: List[Dict[str, Any]],
        terminal: str,
        date_str: str,
        gate: Optional[str],
        context: Dict[str, Any],
        trace_id: str,
        user_role: str
    ) -> Dict[str, Any]:
        """Build response with slot recommendations."""
        # Get carrier score if available
        carrier_score = None
        carrier_id = context.get("carrier_id") or context.get("entities", {}).get("carrier_id")
        
        if carrier_id:
            try:
                from app.tools.carrier_service_client import get_carrier_stats
                from app.algorithms.carrier_scoring import score_carrier
                
                stats = await get_carrier_stats(
                    carrier_id=str(carrier_id),
                    auth_header=self.get_auth_header(context),
                    request_id=trace_id[:8]
                )
                score_result = score_carrier(stats)
                carrier_score = score_result["score"]
            except Exception:
                logger.debug(f"[{trace_id[:8]}] Could not get carrier score for recommendations")
        
        # Run recommender
        requested = {
            "start": f"{date_str} 09:00:00",  # Default morning time
            "terminal": terminal,
            "gate": gate
        }
        
        result = recommend_slots(
            requested=requested,
            candidates=slots,
            carrier_score=carrier_score
        )
        
        recommended = result["recommended"]
        # FIX: Proper indentation
        strategy = result["strategy"]
        overall_reasons = result["reasons"]
        
        # Build message
        if not recommended:
            message = f"Unfortunately, there are no available slots at terminal {terminal} on {date_str}."
        else:
            message_parts = [
                f"Here are the recommended slots for terminal {terminal} on {date_str}:\n"
            ]
            
            for i, slot in enumerate(recommended[:5], 1):
                message_parts.append(
                    f"{i}. {slot['start']} - {slot['end']} "
                    f"(Gate {slot['gate']}, {slot['remaining']}/{slot['capacity']} available)"
                )
                if slot.get("rank_reasons"):
                    message_parts.append(f"   → {', '.join(slot['rank_reasons'][:2])}")
            
            if overall_reasons:
                message_parts.append(f"\nStrategy: {', '.join(overall_reasons)}")
            
            message = "\n".join(message_parts)
        
        # Build data
        data = {
            "terminal": terminal,
            "date": date_str,
            "gate": gate,
            "total_slots": len(slots),
            "recommended_slots": recommended,
            "strategy": strategy,
            "carrier_score": carrier_score
        }
        
        # Build proofs
        proofs = {
            "trace_id": trace_id,
            "sources": [{
                "type": "slot_service",
                "service": SLOT_SERVICE_URL,
                "endpoint": SLOT_AVAILABILITY_PATH
            }],
            "request_id": trace_id[:8],
            "user_role": user_role,
            "algorithm": "deterministic_slot_ranking"
        }
        
        return {
            "message": message,
            "data": data,
            "proofs": proofs
        }

    def _build_availability_response(
        self,
        slots: List[Dict[str, Any]],
        terminal: str,
        date_str: str,
        trace_id: str,
        user_role: str
    ) -> Dict[str, Any]:
        """Build simple availability response."""
        total_remaining = sum(s.get("remaining", 0) for s in slots)
        total_capacity = sum(s.get("capacity", 1) for s in slots)
        
        if not slots:
            message = f"No slots found for terminal {terminal} on {date_str}."
        elif total_remaining == 0:
            message = f"All slots at terminal {terminal} are fully booked on {date_str}."
        else:
            message = (
                f"Terminal {terminal} on {date_str} has {total_remaining}/{total_capacity} "
                f"total capacity available across {len(slots)} time slots."
            )
        
        data = {
            "terminal": terminal,
            "date": date_str,
            "total_slots": len(slots),
            "total_remaining": total_remaining,
            "total_capacity": total_capacity,
            "slots": slots
        }
        
        proofs = {
            "trace_id": trace_id,
            "sources": [{
                "type": "slot_service",
                "service": SLOT_SERVICE_URL,
                "endpoint": SLOT_AVAILABILITY_PATH
            }],
            "request_id": trace_id[:8],
            "user_role": user_role
        }
        
        return {
            "message": message,
            "data": data,
            "proofs": proofs
        }

    def _handle_slot_service_error(
        self,
        http_exception: HTTPException,
        terminal: str,
        trace_id: str
    ) -> Dict[str, Any]:
        """Handle HTTP exceptions from slot service."""
        status_code = http_exception.status_code
        
        if status_code == 401:
            message = "Authentication required to check slot availability. Please log in."
            error_type = "Unauthorized"
        elif status_code == 403:
            message = "You don't have permission to view slot availability."
            error_type = "Forbidden"
        else:
            message = "Slot service is temporarily unavailable. Please try again later."
            error_type = "ServiceUnavailable"
        
        return self.error_response(
            message=message,
            trace_id=trace_id,
            error_type=error_type,
            status_code=status_code
        )

    def _return_missing_backend_error(
        self,
        terminal: str,
        date_str: str,
        trace_id: str
    ) -> Dict[str, Any]:
        """Return helpful error when slot availability endpoint missing."""
        message = (
            f"I cannot check slot availability for terminal {terminal} because the slot service API is not yet available.\n\n"
            "To enable slot availability queries, please implement the following backend endpoint:\n"
            f"• Slot Availability: GET {SLOT_SERVICE_URL}{SLOT_AVAILABILITY_PATH}\n"
            "  Parameters: terminal, date, gate (optional)"
        )
        
        data = {
            "error": "backend_not_available",
            "terminal": terminal,
            "date": date_str,
            "missing_endpoints": [{
                "service": "slot_service",
                "url": f"{SLOT_SERVICE_URL}{SLOT_AVAILABILITY_PATH}",
                "description": "Endpoint for querying slot availability",
                "required_params": ["terminal", "date"],
                "optional_params": ["gate"]
            }],
            "recommendation": "Implement slot availability endpoint to enable this feature"
        }
        
        return {
            "message": message,
            "data": data,
            "proofs": {
                "trace_id": trace_id,
                "status": "failed",
                "reason": "missing_backend_endpoint"
            }
        }
