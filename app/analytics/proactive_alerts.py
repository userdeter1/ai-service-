"""
Proactive Alerts Generation

Generates operational alerts based on real-time conditions:
- Capacity alerts (high utilization, critical thresholds)
- Traffic alerts (peak forecasts)
- Anomaly alerts (incident spikes)
- Carrier risk alerts (low-tier carriers with bookings)
- No-show risk alerts (high-risk bookings detected)

Uses stress index, model predictions, and threshold rules.
"""

import logging
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Import thresholds and models
from app.constants.thresholds import (
    CRITICAL_CAPACITY_THRESHOLD,
    HIGH_CAPACITY_THRESHOLD,
    MEDIUM_CAPACITY_THRESHOLD,
    ANOMALY_SPIKE_THRESHOLD,
    ANOMALY_SEVERITY_HIGH,
    STRESS_HIGH_MAX,
    STRESS_MEDIUM_MAX,
    LOW_CARRIER_SCORE_THRESHOLD
)


# ============================================================================
# Alert Generation
# ============================================================================

async def generate_alerts(
    terminal: str,
    target_date: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    min_severity: str = "medium"
) -> List[Dict[str, Any]]:
    """
    Generate proactive operational alerts based on current conditions.
    
    Args:
        terminal: Terminal identifier
        target_date: Target date (YYYY-MM-DD)
        context: Additional context (auth, trace_id, etc.)
        min_severity: Minimum severity filter ("low", "medium", "high", "critical")
    
    Returns:
        List of alert dictionaries:
        [
            {
                "id": "ALERT-{uuid}",
                "type": "capacity|traffic|anomaly|carrier_risk|no_show_risk|stress",
                "severity": "low|medium|high|critical",
                "title": str,
                "message": str,
                "recommended_actions": [str...],
                "evidence": {...},
                "created_at": ISO timestamp
            }
        ]
    """
    context = context or {}
    trace_id = context.get("trace_id", "unknown")
    auth_header = context.get("auth_header")
    
    logger.info(f"[{trace_id[:8]}] Generating alerts for terminal {terminal}")
    
    alerts = []
    
    # ========================================================================
    # 1. Check Stress Index
    # ========================================================================
    
    try:
        from app.analytics.stress_index import compute_stress_index
        
        stress_result = await compute_stress_index(
            terminal=terminal,
            target_date=target_date,
            context=context
        )
        
        stress_index = stress_result.get("stress_index", 0)
        stress_level = stress_result.get("level", "low")
        
        # Generate stress alert if high/critical
        if stress_index > STRESS_MEDIUM_MAX:
            severity = "critical" if stress_index > STRESS_HIGH_MAX else "high"
            
            alerts.append({
                "id": f"ALERT-{uuid.uuid4().hex[:8].upper()}",
                "type": "stress",
                "severity": severity,
                "title": f"High Stress Level at Terminal {terminal}",
                "message": f"Terminal {terminal} is experiencing {stress_level} stress (index: {stress_index}/100). {stress_result.get('reasons', [''])[0] if stress_result.get('reasons') else ''}",
                "recommended_actions": stress_result.get("recommendations", []),
                "evidence": {
                    "stress_index": stress_index,
                    "drivers": stress_result.get("drivers", {}),
                    "terminal": terminal
                },
                "created_at": datetime.utcnow().isoformat() + "Z"
            })
    
    except Exception as e:
        logger.warning(f"[{trace_id[:8]}] Failed to check stress index: {e}")
    
    # ========================================================================
    # 2. Check Capacity Thresholds
    # ========================================================================
    
    try:
        from app.tools.analytics_data_client import get_capacity_data
        
        capacity_data = await get_capacity_data(
            terminal=terminal,
            date_from=target_date,
            auth_header=auth_header,
            trace_id=trace_id
        )
        
        utilization = capacity_data.get("utilization", 0.0)
        remaining = capacity_data.get("total_remaining", 0)
        
        # Critical capacity alert
        if utilization >= CRITICAL_CAPACITY_THRESHOLD:
            alerts.append({
                "id": f"ALERT-{uuid.uuid4().hex[:8].upper()}",
                "type": "capacity",
                "severity": "critical",
                "title": f"Critical Capacity at Terminal {terminal}",
                "message": f"Terminal {terminal} is at {utilization*100:.0f}% capacity with only {remaining} slot(s) remaining. Immediate action required.",
                "recommended_actions": [
                    "Open additional time slots immediately",
                    "Redirect new bookings to alternative terminals",
                    "Contact operations team for capacity expansion"
                ],
                "evidence": {
                    "utilization": round(utilization, 3),
                    "remaining_slots": remaining,
                    "threshold": CRITICAL_CAPACITY_THRESHOLD,
                    "terminal": terminal
                },
                "created_at": datetime.utcnow().isoformat() + "Z"
            })
        
        # High capacity alert
        elif utilization >= HIGH_CAPACITY_THRESHOLD:
            alerts.append({
                "id": f"ALERT-{uuid.uuid4().hex[:8].upper()}",
                "type": "capacity",
                "severity": "high",
                "title": f"High Capacity Utilization at Terminal {terminal}",
                "message": f"Terminal {terminal} is at {utilization*100:.0f}% capacity. {remaining} slot(s) remaining.",
                "recommended_actions": [
                    "Monitor slot availability closely",
                    "Consider opening additional slots",
                    "Prepare backup terminals if needed"
                ],
                "evidence": {
                    "utilization": round(utilization, 3),
                    "remaining_slots": remaining,
                    "threshold": HIGH_CAPACITY_THRESHOLD,
                    "terminal": terminal
                },
                "created_at": datetime.utcnow().isoformat() + "Z"
            })
        
        # Medium capacity warning
        elif utilization >= MEDIUM_CAPACITY_THRESHOLD:
            alerts.append({
                "id": f"ALERT-{uuid.uuid4().hex[:8].upper()}",
                "type": "capacity",
                "severity": "medium",
                "title": f"Moderate Capacity at Terminal {terminal}",
                "message": f"Terminal {terminal} is at {utilization*100:.0f}% capacity.",
                "recommended_actions": [
                    "Continue normal operations",
                    "Watch for capacity trends"
                ],
                "evidence": {
                    "utilization": round(utilization, 3),
                    "remaining_slots": remaining,
                    "terminal": terminal
                },
                "created_at": datetime.utcnow().isoformat() + "Z"
            })
    
    except Exception as e:
        logger.warning(f"[{trace_id[:8]}] Failed to check capacity: {e}")
    
    # ========================================================================
    # 3. Check Traffic Forecast
    # ========================================================================
    
    try:
        from app.tools.analytics_data_client import get_traffic_forecast
        
        traffic_data = await get_traffic_forecast(
            terminal=terminal,
            target_date=target_date,
            auth_header=auth_header,
            trace_id=trace_id
        )
        
        traffic_intensity = traffic_data.get("intensity", 0.0)
        peak_hour = traffic_data.get("peak_hour", "unknown")
        
        # High traffic alert (> 75%)
        if traffic_intensity >= 0.75:
            alerts.append({
                "id": f"ALERT-{uuid.uuid4().hex[:8].upper()}",
                "type": "traffic",
                "severity": "high",
                "title": f"High Traffic Expected at Terminal {terminal}",
                "message": f"Traffic forecast shows {traffic_intensity*100:.0f}% intensity. Peak expected around {peak_hour}.",
                "recommended_actions": [
                    "Allocate additional staff for peak periods",
                    "Prepare for increased processing times",
                    "Ensure all gates are operational"
                ],
                "evidence": {
                    "intensity": round(traffic_intensity, 3),
                    "peak_hour": peak_hour,
                    "terminal": terminal
                },
                "created_at": datetime.utcnow().isoformat() + "Z"
            })
    
    except Exception as e:
        logger.warning(f"[{trace_id[:8]}] Failed to check traffic: {e}")
    
    # ========================================================================
    # 4. Check Anomalies
    # ========================================================================
    
    try:
        from app.tools.analytics_data_client import get_recent_anomalies
        
        anomaly_data = await get_recent_anomalies(
            terminal=terminal,
            target_date=target_date,
            hours=6,
            auth_header=auth_header,
            trace_id=trace_id
        )
        
        anomaly_count = anomaly_data.get("count", 0)
        anomaly_severity = anomaly_data.get("severity_avg", 0.0)
        
        # Anomaly spike alert
        if anomaly_count >= ANOMALY_SPIKE_THRESHOLD:
            severity = "critical" if anomaly_severity >= ANOMALY_SEVERITY_HIGH else "high"
            
            alerts.append({
                "id": f"ALERT-{uuid.uuid4().hex[:8].upper()}",
                "type": "anomaly",
                "severity": severity,
                "title": f"Anomaly Spike Detected at Terminal {terminal}",
                "message": f"{anomaly_count} anomaly event(s) detected in the last 6 hours. Average severity: {anomaly_severity*100:.0f}%.",
                "recommended_actions": [
                    "Investigate anomaly root causes immediately",
                    "Review system logs and sensor data",
                    "Check for equipment malfunctions",
                    "Notify technical support team"
                ],
                "evidence": {
                    "anomaly_count": anomaly_count,
                    "severity_avg": round(anomaly_severity, 3),
                    "threshold": ANOMALY_SPIKE_THRESHOLD,
                    "terminal": terminal
                },
                "created_at": datetime.utcnow().isoformat() + "Z"
            })
    
    except Exception as e:
        logger.warning(f"[{trace_id[:8]}] Failed to check anomalies: {e}")
    
    # ========================================================================
    # 5. Check Carrier Risks (uses carrier_scoring model if available)
    # ========================================================================
    
    try:
        from app.models.loader import get_model
        
        # Try to get carrier scoring model
        carrier_model = get_model("carrier_scoring")
        
        if carrier_model:
            # Get recent bookings for this terminal
            from app.tools.analytics_data_client import get_bookings_summary
            
            bookings_data = await get_bookings_summary(
                terminal=terminal,
                date_from=target_date,
                auth_header=auth_header,
                trace_id=trace_id
            )
            
            # Check if there are confirmed bookings
            confirmed = bookings_data.get("by_status", {}).get("confirmed", 0)
            
            # Placeholder: In real implementation, would check individual carrier scores
            # For now, generate warning if we have bookings
            if confirmed > 0:
                alerts.append({
                    "id": f"ALERT-{uuid.uuid4().hex[:8].upper()}",
                    "type": "carrier_risk",
                    "severity": "medium",
                    "title": f"Carrier Performance Monitoring",
                    "message": f"{confirmed} confirmed booking(s) at terminal {terminal}. Monitor carrier performance.",
                    "recommended_actions": [
                        "Review carrier reliability scores",
                        "Prioritize high-tier carriers for critical slots",
                        "Apply time buffers for low-tier carriers"
                    ],
                    "evidence": {
                        "confirmed_bookings": confirmed,
                        "terminal": terminal
                    },
                    "created_at": datetime.utcnow().isoformat() + "Z"
                })
    
    except Exception as e:
        logger.debug(f"[{trace_id[:8]}] Carrier risk check skipped: {e}")
    
    # ========================================================================
    # 6. Check No-Show Risks (uses driver_noshow_risk model if available)
    # ========================================================================
    
    try:
        from app.models.loader import get_model
        
        # Try to get no-show risk model
        noshow_model = get_model("driver_noshow_risk")
        
        if noshow_model:
            # Placeholder: In real implementation, would run predictions on upcoming bookings
            # For now, just note that no-show monitoring is active
            logger.debug(f"[{trace_id[:8]}] No-show risk monitoring active")
    
    except Exception as e:
        logger.debug(f"[{trace_id[:8]}] No-show risk check skipped: {e}")
    
    # ========================================================================
    # Filter by Minimum Severity
    # ========================================================================
    
    severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    min_level = severity_order.get(min_severity, 1)
    
    filtered_alerts = [
        alert for alert in alerts
        if severity_order.get(alert.get("severity", "low"), 0) >= min_level
    ]
    
    logger.info(f"[{trace_id[:8]}] Generated {len(filtered_alerts)} alert(s) (filtered by {min_severity}+)")
    
    return filtered_alerts


# ============================================================================
# Helper Functions
# ============================================================================

def alert_severity_score(severity: str) -> int:
    """Convert severity string to numeric score for sorting."""
    return {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(severity, 0)
