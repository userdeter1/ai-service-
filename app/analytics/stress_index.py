"""
Stress Index Computation

Computes real-time stress/congestion index (0-100) for terminals/gates based on:
- Capacity pressure (slot utilization)
- Traffic pressure (forecast intensity)
- Anomaly pressure (recent incidents)
- Queue pressure (booking backlog)

All computations are deterministic and explainable.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)

# Import thresholds
from app.constants.thresholds import (
    STRESS_LOW_MAX,
    STRESS_MEDIUM_MAX,
    STRESS_HIGH_MAX,
    CRITICAL_CAPACITY_THRESHOLD,
    HIGH_CAPACITY_THRESHOLD
)


# ============================================================================
# Stress Index Computation
# ============================================================================

async def compute_stress_index(
    terminal: str,
    target_date: Optional[str] = None,
    gate: Optional[str] = None,
    horizon_hours: int = 6,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Compute stress index for terminal/gate with explainable drivers.
    
    Args:
        terminal: Terminal identifier (A, B, C, etc.)
        target_date: Target date (YYYY-MM-DD), defaults to today
        gate: Optional gate filter
        horizon_hours: Forecast horizon (default 6 hours)
        context: Additional context (auth, trace_id, etc.)
    
    Returns:
        {
            "stress_index": float (0-100),
            "level": "low|medium|high|critical",
            "drivers": {
                "capacity_pressure": float (0-100),
                "traffic_pressure": float (0-100),
                "anomaly_pressure": float (0-100),
                "queue_pressure": float (0-100)
            },
            "reasons": [str...],
            "recommendations": [str...],
            "metadata": {...},
            "data_quality": {
                "mode": "real|mvp",
                "missing": [str...],
                "sources": [str...]
            },
            "computed_at": ISO timestamp
        }
    """
    context = context or {}
    trace_id = context.get("trace_id", "unknown")
    auth_header = context.get("auth_header")
    
    logger.info(f"[{trace_id[:8]}] Computing stress index for terminal {terminal}")
    
    # Default to today if no date provided
    if not target_date:
        target_date = date.today().isoformat()
    
    # Calculate date range for analysis
    date_from = target_date
    date_to = (datetime.fromisoformat(target_date) + timedelta(days=1)).isoformat()[:10]
    
    # Collect data from analytics client
    missing_sources = []
    sources = []
    
    # 1. Get capacity data
    try:
        from app.tools.analytics_data_client import get_capacity_data
        
        capacity_data = await get_capacity_data(
            terminal=terminal,
            date_from=date_from,
            date_to=date_to,
            auth_header=auth_header,
            trace_id=trace_id
        )
        
        if capacity_data.get("data_quality") == "real":
            sources.append("slot_service")
        else:
            missing_sources.append("slot_service")
    except Exception as e:
        logger.warning(f"[{trace_id[:8]}] Failed to get capacity data: {e}")
        capacity_data = {"total_capacity": 100, "total_remaining": 50, "utilization": 0.5, "data_quality": "mvp"}
        missing_sources.append("slot_service")
    
    # 2. Get traffic forecast
    try:
        from app.tools.analytics_data_client import get_traffic_forecast
        
        traffic_data = await get_traffic_forecast(
            terminal=terminal,
            target_date=target_date,
            auth_header=auth_header,
            trace_id=trace_id
        )
        
        if traffic_data.get("data_quality") == "real":
            sources.append("traffic_service")
        else:
            missing_sources.append("traffic_service")
    except Exception as e:
        logger.warning(f"[{trace_id[:8]}] Failed to get traffic forecast: {e}")
        traffic_data = {"intensity": 0.5, "data_quality": "mvp"}
        missing_sources.append("traffic_service")
    
    # 3. Get recent anomalies
    try:
        from app.tools.analytics_data_client import get_recent_anomalies
        
        anomaly_data = await get_recent_anomalies(
            terminal=terminal,
            target_date=target_date,
            hours=horizon_hours,
            auth_header=auth_header,
            trace_id=trace_id
        )
        
        if anomaly_data.get("data_quality") == "real":
            sources.append("anomaly_service")
        else:
            missing_sources.append("anomaly_service")
    except Exception as e:
        logger.warning(f"[{trace_id[:8]}] Failed to get anomaly data: {e}")
        anomaly_data = {"count": 0, "severity_avg": 0.0, "data_quality": "mvp"}
        missing_sources.append("anomaly_service")
    
    # 4. Get bookings summary for queue pressure
    try:
        from app.tools.analytics_data_client import get_bookings_summary
        
        bookings_data = await get_bookings_summary(
            terminal=terminal,
            date_from=date_from,
            date_to=date_to,
            auth_header=auth_header,
            trace_id=trace_id
        )
        
        if bookings_data.get("data_quality") == "real":
            sources.append("booking_service")
        else:
            missing_sources.append("booking_service")
    except Exception as e:
        logger.warning(f"[{trace_id[:8]}] Failed to get bookings data: {e}")
        bookings_data = {"total": 0, "by_status": {"pending": 0}, "data_quality": "mvp"}
        missing_sources.append("booking_service")
    
    # ========================================================================
    # Compute Stress Drivers (Each 0-100)
    # ========================================================================
    
    # Driver 1: Capacity Pressure (40% weight)
    # Based on slot utilization
    utilization = capacity_data.get("utilization", 0.5)
    capacity_pressure = min(100, utilization * 100)
    
    # Driver 2: Traffic Pressure (30% weight)
    # Based on traffic forecast intensity
    traffic_intensity = traffic_data.get("intensity", 0.5)
    traffic_pressure = min(100, traffic_intensity * 100)
    
    # Driver 3: Anomaly Pressure (20% weight)
    # Based on recent anomaly count and severity
    anomaly_count = anomaly_data.get("count", 0)
    anomaly_severity = anomaly_data.get("severity_avg", 0.0)
    
    # Scale: 0 anomalies = 0%, 5+ anomalies = 100%
    anomaly_count_score = min(100, (anomaly_count / 5.0) * 100)
    # Combine count and severity
    anomaly_pressure = min(100, (anomaly_count_score * 0.7) + (anomaly_severity * 100 * 0.3))
    
    # Driver 4: Queue Pressure (10% weight)
    # Based on pending bookings vs capacity
    total_bookings = bookings_data.get("total", 0)
    pending_bookings = bookings_data.get("by_status", {}).get("pending", 0)
    total_capacity = capacity_data.get("total_capacity", 100)
    
    if total_capacity > 0:
        queue_ratio = pending_bookings / total_capacity
        queue_pressure = min(100, queue_ratio * 100)
    else:
        queue_pressure = 0
    
    # ========================================================================
    # Compute Composite Stress Index (Weighted Average)
    # ========================================================================
    
    stress_index = (
        capacity_pressure * 0.40 +
        traffic_pressure * 0.30 +
        anomaly_pressure * 0.20 +
        queue_pressure * 0.10
    )
    
    stress_index = round(stress_index, 1)
    
    # ========================================================================
    # Determine Stress Level
    # ========================================================================
    
    if stress_index <= STRESS_LOW_MAX:
        level = "low"
    elif stress_index <= STRESS_MEDIUM_MAX:
        level = "medium"
    elif stress_index <= STRESS_HIGH_MAX:
        level = "high"
    else:
        level = "critical"
    
    # ========================================================================
    # Generate Explanations and Recommendations
    # ========================================================================
    
    reasons = []
    recommendations = []
    
    # Capacity reasons
    if capacity_pressure >= 90:
        reasons.append(f"Capacity almost full ({utilization*100:.0f}% utilized)")
        recommendations.append("Consider opening additional time slots or gates")
    elif capacity_pressure >= 75:
        reasons.append(f"High capacity utilization ({utilization*100:.0f}%)")
        recommendations.append("Monitor slot availability closely")
    elif capacity_pressure < 30:
        reasons.append(f"Low capacity utilization ({utilization*100:.0f}%)")
    
    # Traffic reasons
    if traffic_pressure >= 75:
        reasons.append(f"High traffic intensity expected ({traffic_intensity*100:.0f}%)")
        recommendations.append("Prepare for peak traffic periods")
    elif traffic_pressure >= 50:
        reasons.append(f"Moderate traffic forecast ({traffic_intensity*100:.0f}%)")
    
    # Anomaly reasons
    if anomaly_count > 0:
        reasons.append(f"{anomaly_count} anomaly event(s) detected in last {horizon_hours}h")
        if anomaly_severity > 0.7:
            recommendations.append("Investigate high-severity anomalies immediately")
        elif anomaly_count >= 3:
            recommendations.append("Review recent anomaly patterns")
    
    # Queue reasons
    if pending_bookings > 0:
        reasons.append(f"{pending_bookings} pending booking(s)")
        if queue_pressure > 50:
            recommendations.append("Expedite pending booking confirmations")
    
    # General recommendations by level
    if level == "critical":
        recommendations.insert(0, "URGENT: Implement congestion mitigation measures")
    elif level == "high":
        recommendations.insert(0, "Consider proactive load balancing")
    elif level == "low":
        recommendations.append("Continue normal operations")
    
    # ========================================================================
    # Data Quality Assessment
    # ========================================================================
    
    data_mode = "real" if len(missing_sources) == 0 else "mvp" if len(missing_sources) >= 3 else "hybrid"
    
    # ========================================================================
    # Return Result
    # ========================================================================
    
    result = {
        "stress_index": stress_index,
        "level": level,
        "drivers": {
            "capacity_pressure": round(capacity_pressure, 1),
            "traffic_pressure": round(traffic_pressure, 1),
            "anomaly_pressure": round(anomaly_pressure, 1),
            "queue_pressure": round(queue_pressure, 1)
        },
        "reasons": reasons,
        "recommendations": recommendations,
        "metadata": {
            "terminal": terminal,
            "gate": gate,
            "date": target_date,
            "horizon_hours": horizon_hours,
            "capacity_utilization": round(utilization, 3),
            "anomaly_count": anomaly_count,
            "pending_bookings": pending_bookings
        },
        "data_quality": {
            "mode": data_mode,
            "missing": missing_sources,
            "sources": sources
        },
        "computed_at": datetime.utcnow().isoformat() + "Z"
    }
    
    logger.info(f"[{trace_id[:8]}] Stress index computed: {stress_index} ({level}) for terminal {terminal}")
    
    return result


# ============================================================================
# Helper Functions
# ============================================================================

def stress_level(index: float) -> str:
    """
    Determine stress level from index value.
    
    Args:
        index: Stress index (0-100)
    
    Returns:
        "low", "medium", "high", or "critical"
    """
    if index <= STRESS_LOW_MAX:
        return "low"
    elif index <= STRESS_MEDIUM_MAX:
        return "medium"
    elif index <= STRESS_HIGH_MAX:
        return "high"
    else:
        return "critical"
