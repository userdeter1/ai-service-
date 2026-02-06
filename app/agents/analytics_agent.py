"""
Analytics Agent

Handles analytics-related intents:
- analytics_stress_index: Compute stress/congestion index for terminals
- analytics_alerts: Generate proactive operational alerts
- analytics_what_if: Simulate operational scenarios

All operations require ADMIN or OPERATOR role.
Returns structured responses with analytics data and recommendations.
"""

import logging
from typing import Dict, Any

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class AnalyticsAgent(BaseAgent):
    """
    Analytics agent for stress index, alerts, and what-if simulations.
    
    Handles intents:
    - analytics_stress_index
    - analytics_alerts
    - analytics_what_if
    
    RBAC: Requires ADMIN or OPERATOR role.
    """
    
    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Core business logic for analytics queries.
        
        Args:
            context: Full context dictionary from orchestrator
        
        Returns:
            Structured response with message, data, and proofs
        """
        trace_id = self.get_trace_id(context)
        intent = context.get("intent", "unknown")
        entities = self.get_entities(context)
        auth_header = self.get_auth_header(context)
        user_role = self.get_user_role(context)
        
        logger.info(f"[{trace_id[:8]}] AnalyticsAgent handling intent: {intent}")
        
        # Require authentication
        if not auth_header:
            return self.error_response(
                message="Authentication required to access analytics features.",
                trace_id=trace_id,
                error_type="Unauthorized"
            )
        
        # Check role authorization (ADMIN/OPERATOR only)
        if user_role not in ("ADMIN", "OPERATOR"):
            return self.error_response(
                message=f"Access denied. Analytics requires ADMIN or OPERATOR role (your role: {user_role}).",
                trace_id=trace_id,
                error_type="Forbidden"
            )
        
        # Route to appropriate analytics function
        if intent == "analytics_stress_index":
            return await self._handle_stress_index(context)
        
        elif intent == "analytics_alerts":
            return await self._handle_alerts(context)
        
        elif intent == "analytics_what_if":
            return await self._handle_what_if(context)
        
        else:
            return self.error_response(
                message=f"Unknown analytics intent: {intent}",
                trace_id=trace_id,
                error_type="UnknownIntent"
            )
    
    async def _handle_stress_index(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle stress index computation request."""
        trace_id = self.get_trace_id(context)
        entities = self.get_entities(context)
        auth_header = self.get_auth_header(context)
        user_role = self.get_user_role(context)
        
        # Extract parameters
        terminal = entities.get("terminal")
        target_date = entities.get("date")
        gate = entities.get("gate")
        
        # Validate terminal required
        if not terminal:
            return self.validation_error(
                message="Please specify a terminal to analyze.",
                suggestion="Try: 'What is the stress level at terminal A?' or 'Compute stress index for terminal B today'",
                missing_field="terminal",
                example="terminal=A",
                trace_id=trace_id
            )
        
        try:
            from app.analytics.stress_index import compute_stress_index
            
            # Compute stress index
            result = await compute_stress_index(
                terminal=terminal,
                target_date=target_date,
                gate=gate,
                context={
                    "trace_id": trace_id,
                    "auth_header": auth_header
                }
            )
            
            # Format message
            stress_index = result.get("stress_index", 0)
            level = result.get("level", "unknown")
            drivers = result.get("drivers", {})
            
            message = self._format_stress_message(terminal, stress_index, level, result)
            
            # Build proofs
            proofs = {
                "trace_id": trace_id,
                "user_role": user_role,
                "sources": result.get("data_quality", {}).get("sources", []),
                "data_quality": result.get("data_quality", {}).get("mode", "mvp")
            }
            
            return self.success_response(
                message=message,
                data=result,
                trace_id=trace_id,
                **proofs
            )
        
        except Exception as e:
            logger.exception(f"[{trace_id[:8]}] Stress index computation failed: {e}")
            return self.error_response(
                message="Failed to compute stress index. Please try again.",
                trace_id=trace_id,
                error_type=type(e).__name__
            )
    
    async def _handle_alerts(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle proactive alerts generation request."""
        trace_id = self.get_trace_id(context)
        entities = self.get_entities(context)
        auth_header = self.get_auth_header(context)
        user_role = self.get_user_role(context)
        
        # Extract parameters
        terminal = entities.get("terminal")
        target_date = entities.get("date")
        
        # Validate terminal required
        if not terminal:
            return self.validation_error(
                message="Please specify a terminal for alerts.",
                suggestion="Try: 'Show alerts for terminal A' or 'What warnings exist for terminal B today?'",
                missing_field="terminal",
                example="terminal=A",
                trace_id=trace_id
            )
        
        try:
            from app.analytics.proactive_alerts import generate_alerts
            
            # Generate alerts
            alerts = await generate_alerts(
                terminal=terminal,
                target_date=target_date,
                context={
                    "trace_id": trace_id,
                    "auth_header": auth_header
                },
                min_severity="medium"
            )
            
            # Format message
            message = self._format_alerts_message(terminal, alerts)
            
            # Build response data
            data = {
                "terminal": terminal,
                "date": target_date,
                "alerts_count": len(alerts),
                "alerts": alerts,
                "summary": self._summarize_alerts(alerts)
            }
            
            # Build proofs
            proofs = {
                "trace_id": trace_id,
                "user_role": user_role,
                "sources": ["stress_index", "capacity_data", "traffic_forecast", "anomalies"]
            }
            
            return self.success_response(
                message=message,
                data=data,
                trace_id=trace_id,
                **proofs
            )
        
        except Exception as e:
            logger.exception(f"[{trace_id[:8]}] Alert generation failed: {e}")
            return self.error_response(
                message="Failed to generate alerts. Please try again.",
                trace_id=trace_id,
                error_type=type(e).__name__
            )
    
    async def _handle_what_if(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle what-if simulation request."""
        trace_id = self.get_trace_id(context)
        entities = self.get_entities(context)
        auth_header = self.get_auth_header(context)
        user_role = self.get_user_role(context)
        message_text = self.get_message(context)
        
        # Extract parameters
        terminal = entities.get("terminal")
        target_date = entities.get("date")
        
        # Try to infer scenario from message
        scenario = self._parse_scenario_from_message(message_text, entities)
        
        if not scenario or not terminal:
            return self.validation_error(
                message="Please specify a scenario to simulate.",
                suggestion="Try: 'What if we shift 20% of bookings from terminal A to B?' or 'What if gate G2 closes for 2 hours?'",
                missing_field="scenario",
                example="shift 20% from A to B",
                trace_id=trace_id
            )
        
        # Add terminal and date to scenario
        scenario["terminal"] = terminal
        scenario["date"] = target_date
        
        try:
            from app.analytics.what_if_simulation import simulate_scenario
            
            # Run simulation
            result = await simulate_scenario(
                scenario=scenario,
                context={
                    "trace_id": trace_id,
                    "auth_header": auth_header
                }
            )
            
            # Format message
            message = self._format_simulation_message(scenario, result)
            
            # Build proofs
            proofs = {
                "trace_id": trace_id,
                "user_role": user_role,
                "confidence": result.get("confidence", "medium"),
                "data_quality": result.get("data_quality", {}).get("mode", "mvp")
            }
            
            return self.success_response(
                message=message,
                data=result,
                trace_id=trace_id,
                **proofs
            )
        
        except Exception as e:
            logger.exception(f"[{trace_id[:8]}] What-if simulation failed: {e}")
            return self.error_response(
                message="Failed to run simulation. Please try again.",
                trace_id=trace_id,
                error_type=type(e).__name__
            )
    
    # ========================================================================
    # Helper Methods - Message Formatting
    # ========================================================================
    
    def _format_stress_message(
        self,
        terminal: str,
        stress_index: float,
        level: str,
        result: Dict[str, Any]
    ) -> str:
        """Format stress index result message."""
        emoji = {"low": "✓", "medium": "⚠", "high": "⚠️", "critical": "🚨"}.get(level, "•")
        
        message = f"{emoji} Terminal {terminal} Stress Index: {stress_index}/100 ({level.upper()})\n\n"
        
        # Add top drivers
        drivers = result.get("drivers", {})
        if drivers:
            message += "**Key Drivers:**\n"
            for driver, value in drivers.items():
                driver_name = driver.replace("_", " ").title()
                message += f"• {driver_name}: {value:.0f}/100\n"
        
        # Add top recommendation
        recommendations = result.get("recommendations", [])
        if recommendations:
            message += f"\n**Recommendation:** {recommendations[0]}"
        
        return message
    
    def _format_alerts_message(self, terminal: str, alerts: List[Dict[str, Any]]) -> str:
        """Format alerts list message."""
        count = len(alerts)
        
        if count == 0:
            return f"✓ No active alerts for terminal {terminal}. Operations normal."
        
        message = f"⚠ {count} alert(s) for terminal {terminal}:\n\n"
        
        for i, alert in enumerate(alerts[:5], 1):  # Show first 5
            severity = alert.get("severity", "unknown").upper()
            title = alert.get("title", "Unknown alert")
            message += f"{i}. [{severity}] {title}\n"
        
        if count > 5:
            message += f"\n... and {count - 5} more alert(s)"
        
        return message
    
    def _format_simulation_message(
        self,
        scenario: Dict[str, Any],
        result: Dict[str, Any]
    ) -> str:
        """Format simulation result message."""
        scenario_type = scenario.get("type", "unknown")
        baseline = result.get("baseline", {})
        simulated = result.get("simulated", {})
        deltas = result.get("deltas", {})
        
        stress_delta = deltas.get("stress_index", 0)
        arrow = "↓" if stress_delta < 0 else "↑" if stress_delta > 0 else "→"
        
        message = f"📊 Simulation Results:\n\n"
        message += f"**Scenario:** {scenario_type.replace('_', ' ').title()}\n"
        message += f"**Baseline Stress:** {baseline.get('stress_index', 0)}/100\n"
        message += f"**Simulated Stress:** {simulated.get('stress_index', 0)}/100 {arrow}\n"
        message += f"**Change:** {stress_delta:+.1f} points\n\n"
        
        # Add top recommendation
        recommendations = result.get("recommendations", [])
        if recommendations:
            message += f"**Key Recommendation:** {recommendations[0]}"
        
        return message
    
    def _summarize_alerts(self, alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize alerts by type and severity."""
        by_type = {}
        by_severity = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        
        for alert in alerts:
            alert_type = alert.get("type", "unknown")
            severity = alert.get("severity", "medium")
            
            by_type[alert_type] = by_type.get(alert_type, 0) + 1
            by_severity[severity] = by_severity.get(severity, 0) + 1
        
        return {
            "by_type": by_type,
            "by_severity": by_severity
        }
    
    def _parse_scenario_from_message(
        self,
        message: str,
        entities: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Parse scenario type and parameters from user message."""
        import re
        
        message_lower = message.lower()
        
        # Shift demand scenario
        if "shift" in message_lower or "move" in message_lower:
            # Extract percentage
            pct_match = re.search(r"(\d+)\s*%", message)
            percentage = int(pct_match.group(1)) if pct_match else 20
            
            # Extract source/target terminals
            terminal_matches = re.findall(r"terminal\s+([A-Z])", message, re.IGNORECASE)
            if len(terminal_matches) >= 2:
                return {
                    "type": "shift_demand",
                    "from_terminal": terminal_matches[0].upper(),
                    "to_terminal": terminal_matches[1].upper(),
                    "percentage": percentage
                }
        
        # Gate closure scenario
        if "close" in message_lower or "closure" in message_lower:
            gate = entities.get("gate")
            
            # Extract duration
            hours_match = re.search(r"(\d+)\s*hours?", message_lower)
            duration_hours = int(hours_match.group(1)) if hours_match else 2
            
            if gate:
                return {
                    "type": "gate_closure",
                    "gate": gate,
                    "duration_hours": duration_hours
                }
        
        # Add capacity scenario
        if "add" in message_lower and ("slot" in message_lower or "capacity" in message_lower):
            # Extract number of slots
            slots_match = re.search(r"(\d+)\s*slot", message_lower)
            additional_slots = int(slots_match.group(1)) if slots_match else 10
            
            return {
                "type": "add_capacity",
                "additional_slots": additional_slots
            }
        
        return None
