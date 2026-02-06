"""
Traffic Agent - Handles traffic-related queries

Responsibilities:
- Traffic forecast queries
- Congestion alerts
- Peak time predictions

Uses REAL->MVP fallback strategy:
- REAL: Calls traffic model or NestJS traffic endpoint if available
- MVP: Returns helpful error about missing backend endpoints
"""

import logging
from typing import Dict, Any, Optional

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class TrafficAgent(BaseAgent):
    """
    Agent specialized in handling traffic forecast and congestion queries.
    
    Intent mapping: traffic_forecast -> TrafficAgent
    """

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Core business logic for traffic queries.
        
        Args:
            context: Full context dictionary from orchestrator
        
        Returns:
            Structured response with message, data, and proofs
        """
        trace_id = self.get_trace_id(context)
        entities = self.get_entities(context)
        auth_header = self.get_auth_header(context)
        user_role = self.get_user_role(context)
        
        # Extract relevant entities
        terminal = entities.get("terminal")
        date = entities.get("date")
        gate = entities.get("gate")
        
        # Try to use traffic model if available
        try:
            from app.models.loader import get_model, list_models
            
            available_models = list_models()
            
            if "traffic_model" in available_models and available_models["traffic_model"].get("available"):
                # Call traffic model
                model = get_model("traffic_model")
                
                model_input = {
                    "terminal": terminal,
                    "date": date,
                    "gate": gate,
                    "horizon_hours": 24  # Default forecast window
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
                    forecast_data = result["result"]
                    model_proofs = result.get("proofs", {})
                    
                    # Format response
                    message = self._format_forecast_message(forecast_data, terminal, date)
                    
                    return self.success_response(
                        message=message,
                        data=forecast_data,
                        trace_id=trace_id,
                        sources=model_proofs.get("sources", []),
                        model="traffic_model"
                    )
        
        except Exception as e:
            logger.warning(f"[{trace_id[:8]}] Traffic model not available: {e}")
        
        # Try NestJS endpoint
        try:
            from app.tools.nest_client import get_client, NEST_BASE_URL
            
            client = get_client()
            
            params = {}
            if terminal:
                params["terminal"] = terminal
            if date:
                params["date"] = date
            if gate:
                params["gate"] = gate
            
            headers = {}
            if auth_header:
                headers["Authorization"] = auth_header
            headers["x-request-id"] = trace_id[:8]
            
            response = await client.get(
                f"{NEST_BASE_URL}/traffic/forecast",
                params=params,
                headers=headers,
                timeout=5.0
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract forecast from response
                forecast = data.get("data") or data.get("forecast") or data
                
                message = self._format_forecast_message(forecast, terminal, date)
                
                return self.success_response(
                    message=message,
                    data=forecast,
                    trace_id=trace_id,
                    sources=[f"{NEST_BASE_URL}/traffic/forecast"],
                    backend="nestjs"
                )
        
        except Exception as e:
            logger.warning(f"[{trace_id[:8]}] Traffic endpoint not available: {e}")
        
        # MVP Fallback: Feature not implemented
        return self._mvp_response(trace_id, terminal, date)
    
    def _format_forecast_message(
        self,
        forecast: Dict[str, Any],
        terminal: Optional[str],
        date: Optional[str]
    ) -> str:
        """Format forecast data into user-friendly message."""
        location = f"terminal {terminal}" if terminal else "the port"
        time_ref = f"on {date}" if date else "soon"
        
        # Extract key metrics
        peak_hour = forecast.get("peak_hour")
        congestion_level = forecast.get("congestion_level", "moderate")
        
        message = f"Traffic forecast for {location} {time_ref}:"
        
        if peak_hour:
            message += f"\n• Peak traffic expected around {peak_hour}"
        
        message += f"\n• Congestion level: {congestion_level}"
        
        # Add recommendations
        recommendations = forecast.get("recommendations", [])
        if recommendations:
            message += "\n\nRecommendations:"
            for rec in recommendations[:3]:
                message += f"\n• {rec}"
        
        return message
    
    def _mvp_response(
        self,
        trace_id: str,
        terminal: Optional[str],
        date: Optional[str]
    ) -> Dict[str, Any]:
        """Return MVP fallback response when backend not available."""
        message = "Traffic forecasting feature is not yet available."
        
        missing_endpoints = [
            f"GET /traffic/forecast - Traffic prediction endpoint",
            "OR traffic_model in model registry"
        ]
        
        data = {
            "status": "not_implemented",
            "reason": "Backend traffic forecasting service not configured",
            "requested_params": {
                "terminal": terminal,
                "date": date
            },
            "required_endpoints": missing_endpoints,
            "suggested_action": "Contact system administrator to enable traffic forecasting"
        }
        
        return {
            "message": message,
            "data": data,
            "proofs": {
                "trace_id": trace_id,
                "feature": "traffic_forecast",
                "status": "planned"
            }
        }
