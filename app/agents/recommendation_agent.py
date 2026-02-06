"""
Recommendation Agent - Handles high-level recommendation queries

Responsibilities:
- Slot recommendations (delegates to slot_recommendation model)
- Carrier improvement suggestions
- General optimization advice

Integrates with:
- slot_recommendation model via app.models.loader
- carrier_scoring model for context-aware recommendations
"""

import logging
from typing import Dict, Any, Optional

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class RecommendationAgent(BaseAgent):
    """
    Agent specialized in providing recommendations using AI models.
    
    Intent mapping: slot_recommendation -> RecommendationAgent
    
    Delegates to:
    - slot_recommendation model (primary)
    - carrier_scoring model (for context)
    """

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Core business logic for recommendation queries.
        
        Args:
            context: Full context dictionary from orchestrator
        
        Returns:
            Structured response with message, data, and proofs
        """
        trace_id = self.get_trace_id(context)
        entities = self.get_entities(context)
        auth_header = self.get_auth_header(context)
        user_role = self.get_user_role(context)
        
        # Require authentication for personalized recommendations
        if not auth_header:
            return self.error_response(
                message="Authentication required for personalized recommendations.",
                trace_id=trace_id,
                error_type="Unauthorized"
            )
        
        # Extract slot recommendation inputs
        terminal = entities.get("terminal")
        date = entities.get("date")
        gate = entities.get("gate")
        carrier_id = entities.get("carrier_id")
        requested_time = entities.get("requested_time")
        
        # Validate required fields
        if not terminal or not date:
            return self.validation_error(
                message="I need more information to provide recommendations.",
                suggestion="Please specify at least the terminal and date. Example: 'Recommend a slot for terminal A on 2026-02-05'",
                missing_field="terminal or date",
                example="terminal=A, date=2026-02-05",
                trace_id=trace_id
            )
        
        # Use slot_recommendation model
        try:
            from app.models.loader import get_model
            
            model = get_model("slot_recommendation")
            
            model_input = {
                "terminal": terminal,
                "date": date,
                "gate": gate,
                "carrier_id": carrier_id,
                "requested_time": requested_time
            }
            
            model_context = {
                "auth_header": auth_header,
                "trace_id": trace_id,
                "user_role": user_role
            }
            
            result = await model.predict(
                input=model_input,
                context=model_context
            )
            
            if not result.get("ok"):
                error = result.get("error", {})
                error_type = error.get("type", "ModelError")
                
                if error_type == "BackendUnavailable":
                    return self._backend_unavailable_response(trace_id, terminal, date)
                
                return self.error_response(
                    message=error.get("message", "Failed to generate recommendations"),
                    trace_id=trace_id,
                    error_type=error_type
                )
            
            recommendation_data = result["result"]
            model_proofs = result.get("proofs", {})
            
            # Format response message
            message = self._format_recommendations_message(
                recommendation_data,
                terminal,
                date,
                carrier_id
            )
            
            return self.success_response(
                message=message,
                data=recommendation_data,
                trace_id=trace_id,
                sources=model_proofs.get("sources", []),
                model="slot_recommendation",
                mode=model_proofs.get("mode", "real")
            )
        
        except ImportError:
            logger.error(f"[{trace_id[:8]}] Model loader not available")
            return self.error_response(
                message="Recommendation service is currently unavailable. Please try again later.",
                trace_id=trace_id,
                error_type="ServiceUnavailable"
            )
        
        except Exception as e:
            logger.exception(f"[{trace_id[:8]}] Recommendation error: {e}")
            return self.error_response(
                message="Failed to generate recommendations. Please try again.",
                trace_id=trace_id,
                error_type=type(e).__name__
            )
    
    def _format_recommendations_message(
        self,
        data: Dict[str, Any],
        terminal: str,
        date: str,
        carrier_id: Optional[str]
    ) -> str:
        """Format recommendation data into user-friendly message."""
        recommended = data.get("recommended", [])
        count = len(recommended)
        
        if count == 0:
            return f"No available slots found for terminal {terminal} on {date}. Please try a different date or terminal."
        
        message = f"I found {count} recommended slot(s) for terminal {terminal} on {date}:"
        
        # Show top 3 recommendations
        for i, slot in enumerate(recommended[:3], 1):
            start_time = slot.get("start") or slot.get("start_time", "")
            capacity = slot.get("remaining_capacity", slot.get("capacity", ""))
            score = slot.get("rank_score", 0)
            
            message += f"\n\n{i}. {start_time}"
            if capacity:
                message += f" (Capacity: {capacity})"
            if score:
                message += f" - Score: {score:.2f}/100"
            
            # Add reasons
            reasons = slot.get("reasons", [])
            if reasons:
                message += "\n   Reasons:"
                for reason in reasons[:2]:
                    message += f"\n   • {reason}"
        
        # Add carrier-specific advice
        if carrier_id:
            carrier_score = data.get("carrier_context", {}).get("score")
            if carrier_score and carrier_score < 60:
                message += "\n\n⚠️ Tip: Your carrier score is low. Consider booking earlier slots to avoid delays."
        
        return message
    
    def _backend_unavailable_response(
        self,
        trace_id: str,
        terminal: str,
        date: str
    ) -> Dict[str, Any]:
        """Return response when backend services are unavailable."""
        message = "Recommendation service temporarily unavailable."
        
        data = {
            "status": "backend_unavailable",
            "reason": "Slot availability service is not responding",
            "requested_params": {
                "terminal": terminal,
                "date": date
            },
            "suggested_action": "Please try again in a moment, or contact support if the issue persists"
        }
        
        return {
            "message": message,
            "data": data,
            "proofs": {
                "trace_id": trace_id,
                "status": "failed"
            }
        }
