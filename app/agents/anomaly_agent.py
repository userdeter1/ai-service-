"""
Anomaly Agent - Handles anomaly detection queries

Responsibilities:
- Query recent anomalies (no-shows, delays, patterns)
- Analyze anomaly patterns
- Provide explanations for detected anomalies

Uses REAL->MVP fallback strategy:
- REAL: Calls NestJS anomalies endpoint or anomaly model if available
- MVP: Returns helpful error about missing backend endpoints
"""

import logging
from typing import Dict, Any, Optional, List

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class AnomalyAgent(BaseAgent):
    """
    Agent specialized in handling anomaly detection and explanation queries.
    
    Intent mapping: anomaly_detection -> AnomalyAgent
    """

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Core business logic for anomaly queries.
        
        Args:
            context: Full context dictionary from orchestrator
        
        Returns:
            Structured response with message, data, and proofs
        """
        trace_id = self.get_trace_id(context)
        entities = self.get_entities(context)
        auth_header = self.get_auth_header(context)
        user_role = self.get_user_role(context)
        
        # Require authentication for anomaly data (sensitive operational intelligence)
        if not auth_header:
            return self.error_response(
                message="Authentication required to access anomaly detection data.",
                trace_id=trace_id,
                error_type="Unauthorized"
            )
        
        # Check role authorization (ADMIN/OPERATOR only)
        if user_role not in ("ADMIN", "OPERATOR"):
            return self.error_response(
                message=f"Access denied. Anomaly detection requires ADMIN or OPERATOR role (your role: {user_role}).",
                trace_id=trace_id,
                error_type="Forbidden"
            )
        
        # Extract filter entities
        terminal = entities.get("terminal")
        carrier_id = entities.get("carrier_id")
        days = 7  # Default lookback
        
        # Try to use anomaly model if available
        try:
            from app.models.loader import get_model, list_models
            
            available_models = list_models()
            
            if "anomaly_model" in available_models and available_models["anomaly_model"].get("available"):
                model = get_model("anomaly_model")
                
                model_input = {
                    "terminal": terminal,
                    "carrier_id": carrier_id,
                    "days": days
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
                
                if result.get("ok"):
                    anomaly_data = result["result"]
                    model_proofs = result.get("proofs", {})
                    
                    message = self._format_anomalies_message(anomaly_data, terminal, days)
                    
                    return self.success_response(
                        message=message,
                        data=anomaly_data,
                        trace_id=trace_id,
                        sources=model_proofs.get("sources", []),
                        model="anomaly_model"
                    )
        
        except Exception as e:
            logger.warning(f"[{trace_id[:8]}] Anomaly model not available: {e}")
        
        # Try NestJS endpoint
        try:
            from app.tools.nest_client import get_client, NEST_BASE_URL
            import httpx
            
            client = get_client()
            
            params = {}
            if terminal:
                params["terminal"] = terminal
            if carrier_id:
                params["carrier_id"] = carrier_id
            params["days"] = days
            params["limit"] = 50
            
            headers = {}
            if auth_header:
                headers["Authorization"] = auth_header
            headers["x-request-id"] = trace_id[:8]
            
            response = await client.get(
                f"{NEST_BASE_URL}/anomalies",
                params=params,
                headers=headers,
                timeout=5.0
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract anomalies from response
                if isinstance(data, dict):
                    anomalies = data.get("data") or data.get("anomalies") or []
                elif isinstance(data, list):
                    anomalies = data
                else:
                    anomalies = []
                
                message = self._format_anomalies_message(
                    {"anomalies": anomalies, "count": len(anomalies)},
                    terminal,
                    days
                )
                
                return self.success_response(
                    message=message,
                    data={
                        "anomalies": anomalies,
                        "total_count": len(anomalies),
                        "terminal": terminal,
                        "days": days
                    },
                    trace_id=trace_id,
                    sources=[f"{NEST_BASE_URL}/anomalies"],
                    backend="nestjs"
                )
            
            elif response.status_code in (404, 501):
                # Endpoint not implemented
                pass
        
        except httpx.TimeoutException:
            logger.warning(f"[{trace_id[:8]}] Anomalies endpoint timeout")
        except Exception as e:
            logger.warning(f"[{trace_id[:8]}] Anomalies endpoint not available: {e}")
        
        # MVP Fallback
        return self._mvp_response(trace_id, terminal, carrier_id, days)
    
    def _format_anomalies_message(
        self,
        data: Dict[str, Any],
        terminal: Optional[str],
        days: int
    ) -> str:
        """Format anomaly data into user-friendly message."""
        anomalies = data.get("anomalies", [])
        count = len(anomalies)
        
        location = f"terminal {terminal}" if terminal else "all terminals"
        
        if count == 0:
            return f"No anomalies detected for {location} in the last {days} days. Everything looks normal!"
        
        message = f"Found {count} anomaly(ies) for {location} in the last {days} days:"
        
        # Group by type
        by_type = {}
        for anomaly in anomalies:
            atype = anomaly.get("type", "unknown")
            by_type[atype] = by_type.get(atype, 0) + 1
        
        message += "\n\nBreakdown by type:"
        for atype, cnt in by_type.items():
            message += f"\n• {atype}: {cnt}"
        
        # Show top 3 most recent
        if anomalies:
            message += "\n\nMost recent:"
            for anomaly in anomalies[:3]:
                desc = anomaly.get("description") or anomaly.get("message", "Anomaly detected")
                timestamp = anomaly.get("timestamp", "")
                message += f"\n• [{timestamp}] {desc}"
        
        return message
    
    def _mvp_response(
        self,
        trace_id: str,
        terminal: Optional[str],
        carrier_id: Optional[str],
        days: int
    ) -> Dict[str, Any]:
        """Return MVP fallback response when backend not available."""
        message = "Anomaly detection feature is not yet available."
        
        missing_endpoints = [
            "GET /anomalies - Anomaly detection endpoint",
            "OR anomaly_model in model registry"
        ]
        
        data = {
            "status": "not_implemented",
            "reason": "Backend anomaly detection service not configured",
            "requested_params": {
                "terminal": terminal,
                "carrier_id": carrier_id,
                "days": days
            },
            "required_endpoints": missing_endpoints,
            "suggested_action": "Contact system administrator to enable anomaly detection"
        }
        
        return {
            "message": message,
            "data": data,
            "proofs": {
                "trace_id": trace_id,
                "feature": "anomaly_detection",
                "status": "planned"
            }
        }
