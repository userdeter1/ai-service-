"""
What-If Simulation

Simulates operational scenarios and predicts impacts on stress index, capacity,
and alerts. Supports multiple scenario types:
- shift_demand: Move % of bookings between terminals
- gate_closure: Close gate for N hours
- add_capacity: Increase slot capacity
- carrier_policy: Deprioritize low-tier carriers

All simulations are deterministic and provide baseline vs simulated comparisons.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from copy import deepcopy

logger = logging.getLogger(__name__)


# ============================================================================
# What-If Simulation
# ============================================================================

async def simulate_scenario(
    scenario: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Simulate operational scenario and predict impacts.
    
    Args:
        scenario: Scenario definition dict:
            {
                "type": "shift_demand|gate_closure|add_capacity|carrier_policy",
                "terminal": str,
                "date": str (YYYY-MM-DD),
                
                # For shift_demand:
                "from_terminal": str,
                "to_terminal": str,
                "percentage": int (0-100),
                
                # For gate_closure:
                "gate": str,
                "duration_hours": int,
                
                # For add_capacity:
                "additional_slots": int,
                
                # For carrier_policy:
                "policy": "deprioritize_low_tier|buffer_risky"
            }
        context: Additional context (auth, trace_id, etc.)
    
    Returns:
        {
            "scenario": {...},  # Input scenario
            "baseline": {
                "stress_index": float,
                "stress_level": str,
                "alerts_count": int,
                "capacity_utilization": float
            },
            "simulated": {
                "stress_index": float,
                "stress_level": str,
                "alerts_count": int,
                "capacity_utilization": float
            },
            "deltas": {
                "stress_index": float,
                "alerts_count": int,
                "capacity_utilization": float
            },
            "recommendations": [str...],
            "confidence": "high|medium|low",
            "data_quality": {...},
            "simulated_at": ISO timestamp
        }
    """
    context = context or {}
    trace_id = context.get("trace_id", "unknown")
    
    scenario_type = scenario.get("type", "unknown")
    terminal = scenario.get("terminal")
    target_date = scenario.get("date")
    
    logger.info(f"[{trace_id[:8]}] Simulating scenario: {scenario_type} for terminal {terminal}")
    
    # ========================================================================
    # 1. Compute Baseline Metrics
    # ========================================================================
    
    try:
        from app.analytics.stress_index import compute_stress_index
        from app.analytics.proactive_alerts import generate_alerts
        from app.tools.analytics_data_client import get_capacity_data
        
        # Baseline stress index
        baseline_stress = await compute_stress_index(
            terminal=terminal,
            target_date=target_date,
            context=context
        )
        
        # Baseline alerts
        baseline_alerts = await generate_alerts(
            terminal=terminal,
            target_date=target_date,
            context=context,
            min_severity="low"
        )
        
        # Baseline capacity
        baseline_capacity = await get_capacity_data(
            terminal=terminal,
            date_from=target_date,
            auth_header=context.get("auth_header"),
            trace_id=trace_id
        )
        
        baseline_metrics = {
            "stress_index": baseline_stress.get("stress_index", 0),
            "stress_level": baseline_stress.get("level", "unknown"),
            "alerts_count": len(baseline_alerts),
            "capacity_utilization": baseline_capacity.get("utilization", 0.0),
            "capacity_remaining": baseline_capacity.get("total_remaining", 0)
        }
        
    except Exception as e:
        logger.error(f"[{trace_id[:8]}] Failed to compute baseline: {e}")
        baseline_metrics = {
            "stress_index": 0,
            "stress_level": "unknown",
            "alerts_count": 0,
            "capacity_utilization": 0.5,
            "capacity_remaining": 50
        }
    
    # ========================================================================
    # 2. Simulate Scenario Impact
    # ========================================================================
    
    simulated_metrics = deepcopy(baseline_metrics)
    recommendations = []
    confidence = "medium"
    
    if scenario_type == "shift_demand":
        # Shift X% of demand from terminal A to B
        from_terminal = scenario.get("from_terminal", terminal)
        to_terminal = scenario.get("to_terminal")
        percentage = scenario.get("percentage", 0)
        
        if from_terminal and to_terminal and percentage > 0:
            # Simulate reduction in source terminal stress
            reduction_factor = percentage / 100.0
            
            # Reduce stress proportionally
            simulated_metrics["stress_index"] = baseline_metrics["stress_index"] * (1 - reduction_factor * 0.5)
            simulated_metrics["capacity_utilization"] = baseline_metrics["capacity_utilization"] * (1 - reduction_factor)
            
            # Recalculate stress level
            simulated_metrics["stress_level"] = _stress_level_from_index(simulated_metrics["stress_index"])
            
            # Estimate alert reduction
            if simulated_metrics["capacity_utilization"] < 0.75:
                simulated_metrics["alerts_count"] = max(0, baseline_metrics["alerts_count"] - 2)
            elif simulated_metrics["capacity_utilization"] < 0.85:
                simulated_metrics["alerts_count"] = max(0, baseline_metrics["alerts_count"] - 1)
            
            recommendations = [
                f"Shift {percentage}% of bookings from {from_terminal} to {to_terminal}",
                f"Expected stress reduction: {baseline_metrics['stress_index'] - simulated_metrics['stress_index']:.1f} points",
                f"Monitor {to_terminal} capacity to ensure it can handle additional load",
                "Communicate changes to affected carriers in advance"
            ]
            
            confidence = "high" if percentage <= 30 else "medium"
        
        else:
            recommendations = ["Invalid shift_demand parameters"]
            confidence = "low"
    
    elif scenario_type == "gate_closure":
        # Close gate for N hours
        gate = scenario.get("gate")
        duration_hours = scenario.get("duration_hours", 2)
        
        if gate and duration_hours > 0:
            # Simulate capacity reduction
            # Assume gate closure reduces capacity by ~20% (typical gate contribution)
            capacity_impact = 0.20
            
            simulated_metrics["capacity_utilization"] = min(1.0, baseline_metrics["capacity_utilization"] / (1 - capacity_impact))
            simulated_metrics["stress_index"] = min(100, baseline_metrics["stress_index"] + (capacity_impact * 100 * 0.4))
            simulated_metrics["stress_level"] = _stress_level_from_index(simulated_metrics["stress_index"])
            
            # Likely increase in alerts if utilization goes critical
            if simulated_metrics["capacity_utilization"] >= 0.90:
                simulated_metrics["alerts_count"] = baseline_metrics["alerts_count"] + 2
            elif simulated_metrics["capacity_utilization"] >= 0.75:
                simulated_metrics["alerts_count"] = baseline_metrics["alerts_count"] + 1
            
            recommendations = [
                f"Gate {gate} closure for {duration_hours}h will increase stress by {simulated_metrics['stress_index'] - baseline_metrics['stress_index']:.1f} points",
                "Redistribute traffic to other gates",
                "Consider postponing non-critical bookings",
                f"Allocate additional staff to remaining gates",
                "Prepare contingency plans if stress exceeds 85"
            ]
            
            confidence = "high"
        
        else:
            recommendations = ["Invalid gate_closure parameters"]
            confidence = "low"
    
    elif scenario_type == "add_capacity":
        # Add N additional slots
        additional_slots = scenario.get("additional_slots", 0)
        
        if additional_slots > 0:
            # Simulate capacity increase
            current_total = baseline_capacity.get("total_capacity", 100)
            new_total = current_total + additional_slots
            
            # Recalculate utilization
            if new_total > 0:
                current_used = current_total * baseline_metrics["capacity_utilization"]
                simulated_metrics["capacity_utilization"] = current_used / new_total
                simulated_metrics["capacity_remaining"] = new_total - current_used
            
            # Reduce stress proportionally
            capacity_improvement = additional_slots / current_total if current_total > 0 else 0
            simulated_metrics["stress_index"] = max(0, baseline_metrics["stress_index"] - (capacity_improvement * 100 * 0.4))
            simulated_metrics["stress_level"] = _stress_level_from_index(simulated_metrics["stress_index"])
            
            # Reduce alerts if utilization improves significantly
            if simulated_metrics["capacity_utilization"] < 0.60:
                simulated_metrics["alerts_count"] = max(0, baseline_metrics["alerts_count"] - 2)
            elif simulated_metrics["capacity_utilization"] < 0.75:
                simulated_metrics["alerts_count"] = max(0, baseline_metrics["alerts_count"] - 1)
            
            recommendations = [
                f"Adding {additional_slots} slot(s) will reduce stress by {baseline_metrics['stress_index'] - simulated_metrics['stress_index']:.1f} points",
                f"New capacity utilization: {simulated_metrics['capacity_utilization']*100:.0f}%",
                "Ensure operational resources are available for new slots",
                "Update booking system with new slot availability"
            ]
            
            confidence = "high"
        
        else:
            recommendations = ["Invalid add_capacity parameters"]
            confidence = "low"
    
    elif scenario_type == "carrier_policy":
        # Apply carrier policy (deprioritize low-tier, buffer risky carriers)
        policy = scenario.get("policy", "deprioritize_low_tier")
        
        if policy == "deprioritize_low_tier":
            # Simulate slight stress reduction by prioritizing high-tier carriers
            simulated_metrics["stress_index"] = max(0, baseline_metrics["stress_index"] - 5)
            simulated_metrics["stress_level"] = _stress_level_from_index(simulated_metrics["stress_index"])
            
            recommendations = [
                "Deprioritize low-tier carriers during peak periods",
                "Apply carrier score >= 60 requirement for critical slots",
                "Expected modest stress reduction (~5 points)",
                "Monitor carrier satisfaction and booking patterns"
            ]
            
            confidence = "medium"
        
        elif policy == "buffer_risky":
            # Simulate buffer time for risky carriers
            simulated_metrics["stress_index"] = max(0, baseline_metrics["stress_index"] - 3)
            simulated_metrics["stress_level"] = _stress_level_from_index(simulated_metrics["stress_index"])
            
            recommendations = [
                "Apply 60-minute buffer for carriers with score < 60",
                "Reduce no-show risk impact on operations",
                "Expected minor stress reduction (~3 points)",
                "Use slot_recommendation algorithm for optimal scheduling"
            ]
            
            confidence = "medium"
        
        else:
            recommendations = ["Unknown carrier policy type"]
            confidence = "low"
    
    else:
        recommendations = [f"Unsupported scenario type: {scenario_type}"]
        confidence = "low"
    
    # ========================================================================
    # 3. Compute Deltas
    # ========================================================================
    
    deltas = {
        "stress_index": round(simulated_metrics["stress_index"] - baseline_metrics["stress_index"], 1),
        "alerts_count": simulated_metrics["alerts_count"] - baseline_metrics["alerts_count"],
        "capacity_utilization": round(simulated_metrics["capacity_utilization"] - baseline_metrics["capacity_utilization"], 3)
    }
    
    # ========================================================================
    # 4. Return Simulation Results
    # ========================================================================
    
    result = {
        "scenario": scenario,
        "baseline": {
            "stress_index": round(baseline_metrics["stress_index"], 1),
            "stress_level": baseline_metrics["stress_level"],
            "alerts_count": baseline_metrics["alerts_count"],
            "capacity_utilization": round(baseline_metrics["capacity_utilization"], 3)
        },
        "simulated": {
            "stress_index": round(simulated_metrics["stress_index"], 1),
            "stress_level": simulated_metrics["stress_level"],
            "alerts_count": simulated_metrics["alerts_count"],
            "capacity_utilization": round(simulated_metrics["capacity_utilization"], 3)
        },
        "deltas": deltas,
        "recommendations": recommendations,
        "confidence": confidence,
        "data_quality": baseline_stress.get("data_quality", {"mode": "mvp"}),
        "simulated_at": datetime.utcnow().isoformat() + "Z"
    }
    
    logger.info(f"[{trace_id[:8]}] Simulation complete: {scenario_type}, delta stress = {deltas['stress_index']}")
    
    return result


# ============================================================================
# Helper Functions
# ============================================================================

def _stress_level_from_index(index: float) -> str:
    """Determine stress level from index value."""
    if index <= 30:
        return "low"
    elif index <= 60:
        return "medium"
    elif index <= 85:
        return "high"
    else:
        return "critical"
