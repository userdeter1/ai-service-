"""
Carrier Score Agent - Handles carrier reliability scoring

Responsibilities:
- Extract carrier ID from user request
- Query real carrier service for stats (with MVP fallback)
- Calculate reliability score using deterministic algorithm
- Provide actionable insights and recommendations

Fallback strategy:
- If carrier stats endpoint missing -> try booking service for carrier's bookings
- If booking service unavailable -> return helpful error with missing endpoints
- MVP fallback caps score at 75 and confidence at 0.6 (limited data quality)
"""

import re
import logging
from typing import Dict, Any, Optional
from fastapi import HTTPException

from app.agents.base_agent import BaseAgent
from app.tools.carrier_service_client import (
    get_carrier_stats,
    is_endpoint_missing,
    CARRIER_SERVICE_URL,
    CARRIER_STATS_PATH
)
from app.algorithms.carrier_scoring import score_carrier

logger = logging.getLogger(__name__)


class CarrierScoreAgent(BaseAgent):
    """Agent specialized in carrier reliability scoring and performance analysis."""

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Core logic for carrier scoring.
        
        Strategy:
        1. Extract carrier_id from context/entities/message
        2. Try REAL carrier stats endpoint
        3. If missing (404/405/501) -> try MVP fallback via booking service
        4. If no data at all -> return helpful error
        """
        trace_id = self.get_trace_id(context)
        entities = self.get_entities(context)
        auth_header = self.get_auth_header(context)
        message = self.get_message(context)
        user_role = self.get_user_role(context)
        
        # Extract carrier ID
        carrier_id = self._extract_carrier_id(context, entities, message)
        
        if not carrier_id:
            return self.validation_error(
                message="I couldn't identify which carrier you're asking about. Please specify a carrier ID.",
                suggestion="Try asking: 'What's the score for carrier 123?' or 'Rate company ID 456'",
                missing_field="carrier_id",
                example="carrier 123",
                trace_id=trace_id
            )
        
        logger.info(f"[{trace_id[:8]}] CarrierScoreAgent processing carrier {carrier_id}")
        
        # Strategy: Try REAL first, then MVP fallback
        try:
            # Attempt REAL carrier stats endpoint
            stats = await get_carrier_stats(
                carrier_id=carrier_id,
                window_days=90,
                auth_header=auth_header,
                request_id=trace_id[:8]
            )
            
            # Success - calculate score
            score_result = score_carrier(stats)
            
            return self._build_success_response(
                carrier_id=carrier_id,
                score_result=score_result,
                trace_id=trace_id,
                user_role=user_role,
                source="carrier_service",
                is_fallback=False
            )
            
        except HTTPException as e:
            # Check if endpoint is missing/unimplemented
            if is_endpoint_missing(e):
                logger.warning(f"[{trace_id[:8]}] Carrier stats endpoint not available, trying MVP fallback")
                return await self._mvp_fallback(carrier_id, auth_header, trace_id, user_role)
            
            # Handle other HTTP errors
            return self._handle_carrier_service_error(e, carrier_id, trace_id)
            
        except Exception as e:
            logger.exception(f"[{trace_id[:8]}] Unexpected error in CarrierScoreAgent: {e}")
            return self.error_response(
                message="I encountered an unexpected error while calculating carrier score. Please try again.",
                trace_id=trace_id,
                error_type=type(e).__name__
            )

    def _extract_carrier_id(
        self,
        context: Dict[str, Any],
        entities: Dict[str, Any],
        message: str
    ) -> Optional[str]:
        """
        Extract carrier ID from multiple possible sources.
        
        Priority:
        1. context["carrier_id"]
        2. entities["carrier_id"]
        3. Parse from message patterns
        """
        # Check context
        carrier_id = context.get("carrier_id")
        if carrier_id:
            return str(carrier_id)
        
        # Check entities
        carrier_id = entities.get("carrier_id")
        if carrier_id:
            return str(carrier_id)
        
        # Parse from message
        # Patterns: "carrier 123", "transporteur 123", "chauffeur 123", "company 123", "ID 123"
        patterns = [
            r"\b(?:carrier|transporteur|chauffeur|company|driver)\s+(?:id\s+)?(\d+)\b",
            r"\bID\s+(\d+)\b",
            r"\b(?:for|score|rate)\s+(\d+)\b"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None

    async def _mvp_fallback(
        self,
        carrier_id: str,
        auth_header: Optional[str],
        trace_id: str,
        user_role: str
    ) -> Dict[str, Any]:
        """
        MVP fallback when carrier stats endpoint is not available.
        
        Strategy:
        - Try to fetch bookings from booking service filtered by carrier
        - Compute basic stats from bookings
        - Cap score at 75 and confidence at 0.6 (limited metrics)
        - If booking service also unavailable, return helpful error
        """
        logger.info(f"[{trace_id[:8]}] Attempting MVP scoring via booking service")
        
        try:
            # Try to get bookings for this carrier
            from app.tools.booking_service_client import (
                BOOKING_SERVICE_URL,
                get_client as get_booking_client
            )
            import os
            import httpx
            
            # Endpoint for carrier bookings (may not exist either)
            booking_by_carrier_path = os.getenv(
                "BOOKING_BY_CARRIER_PATH",
                "/bookings?carrierId={carrier_id}&days={days}"
            )
            url = f"{BOOKING_SERVICE_URL}{booking_by_carrier_path}".format(
                carrier_id=carrier_id,
                days=90
            )
            
            headers = {"Content-Type": "application/json"}
            if auth_header:
                headers["Authorization"] = auth_header
            
            client = get_booking_client()
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            bookings_data = response.json()
            
            # Extract bookings list
            if isinstance(bookings_data, dict):
                bookings = bookings_data.get("data") or bookings_data.get("bookings") or []
            elif isinstance(bookings_data, list):
                bookings = bookings_data
            else:
                bookings = []
            
            # Compute stats from bookings
            stats = self._compute_stats_from_bookings(bookings)
            
            if stats["total_bookings"] == 0:
                return self.error_response(
                    message=f"No booking history found for carrier {carrier_id}. Cannot calculate score without data.",
                    trace_id=trace_id,
                    error_type="InsufficientData",
                    carrier_id=carrier_id
                )
            
            # Calculate score
            score_result = score_carrier(stats)
            
            # MVP HONESTY: Cap score at 75 and confidence at 0.6
            original_score = score_result["score"]
            original_confidence = score_result["confidence"]
            score_result["score"] = min(75.0, score_result["score"])
            score_result["confidence"] = min(0.6, score_result["confidence"])
            
            # Add data quality indicator
            score_result["data_quality"] = stats.get("data_quality", {})
            
            logger.info(
                f"[{trace_id[:8]}] MVP fallback score: {score_result['score']:.1f} "
                f"(capped from {original_score:.1f}), "
                f"confidence: {score_result['confidence']:.2f} (capped from {original_confidence:.2f})"
            )
            
            return self._build_success_response(
                carrier_id=carrier_id,
                score_result=score_result,
                trace_id=trace_id,
                user_role=user_role,
                source="booking_service_mvp",
                is_fallback=True,
                mvp_note="Score computed from booking history with limited metrics (carrier stats service unavailable)"
            )
            
        except httpx.HTTPStatusError as e:
            # Check if booking-by-carrier endpoint is also missing
            if e.response.status_code in (404, 405, 501):
                logger.warning(f"[{trace_id[:8]}] Booking-by-carrier endpoint also unavailable")
                return self._return_missing_backend_error(carrier_id, trace_id, both_missing=True)
            # Other HTTP errors from booking service
            logger.warning(f"[{trace_id[:8]}] MVP fallback failed - booking service error {e.response.status_code}")
            return self._return_missing_backend_error(carrier_id, trace_id, both_missing=False)
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            # Booking service unavailable
            logger.warning(f"[{trace_id[:8]}] MVP fallback failed - booking service unavailable")
            return self._return_missing_backend_error(carrier_id, trace_id, both_missing=False)
        except Exception as e:
            logger.exception(f"[{trace_id[:8]}] MVP fallback error: {e}")
            return self._return_missing_backend_error(carrier_id, trace_id, both_missing=False)

    def _compute_stats_from_bookings(self, bookings: list) -> Dict[str, Any]:
        """
        Compute carrier stats from booking list (MVP fallback).
        
        Expects bookings to have status field with values like:
        - Confirmed, Completed, Cancelled, etc.
        
        Returns stats with data_quality indicator.
        """
        total = len(bookings)
        if total == 0:
            return {
                "total_bookings": 0,
                "completed_bookings": 0,
                "cancelled_bookings": 0,
                "no_shows": 0,
                "late_arrivals": 0,
                "avg_delay_minutes": 0.0,
                "avg_dwell_minutes": 0.0,
                "anomaly_count": 0,
                "last_activity_at": "N/A",
                "data_quality": {
                    "missing_metrics": ["no_shows", "late_arrivals", "avg_delay_minutes", "avg_dwell_minutes", "anomaly_count"],
                    "source": "booking_service_fallback"
                }
            }
        
        completed = 0
        cancelled = 0
        # MVP: Can't determine no-shows/late-arrivals from just status
        # Would need additional fields
        
        for booking in bookings:
            status = str(booking.get("status", "")).lower()
            if status in ("completed", "consumed"):
                completed += 1
            elif status in ("cancelled", "canceled"):
                cancelled += 1
        
        return {
            "total_bookings": total,
            "completed_bookings": completed,
            "cancelled_bookings": cancelled,
            "no_shows": 0,  # MVP: unavailable
            "late_arrivals": 0,  # MVP: unavailable
            "avg_delay_minutes": 0.0,  # MVP: unavailable
            "avg_dwell_minutes": 0.0,  # MVP: unavailable
            "anomaly_count": 0,  # MVP: unavailable
            "last_activity_at": "N/A",
            "data_quality": {
                "missing_metrics": ["no_shows", "late_arrivals", "avg_delay_minutes", "avg_dwell_minutes", "anomaly_count"],
                "source": "booking_service_fallback",
                "note": "Limited metrics from booking history - score capped at 75, confidence at 0.6"
            }
        }

    def _build_success_response(
        self,
        carrier_id: str,
        score_result: Dict[str, Any],
        trace_id: str,
        user_role: str,
        source: str,
        is_fallback: bool,
        mvp_note: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build success response with carrier score."""
        score = score_result["score"]
        tier = score_result["tier"]
        reasons = score_result["reasons"]
        confidence = score_result["confidence"]
        stats_summary = score_result["stats_summary"]
        
        # Build message
        message_parts = [
            f"Carrier {carrier_id} has a reliability score of {score:.1f}/100 (Tier {tier}).\n"
        ]
        
        if mvp_note:
            message_parts.append(f"⚠️ {mvp_note}\n")
        
        if is_fallback:
            message_parts.append("Note: Score is capped at 75/100 and confidence at 60% due to limited metrics.\n")
        
        message_parts.append("\nKey Factors:")
        for reason in reasons:
            message_parts.append(f"• {reason}")
        
        if confidence < 0.7:
            message_parts.append(f"\n⚠️ Confidence: {confidence*100:.0f}% - More data recommended for accurate scoring")
        
        message = "\n".join(message_parts)
        
        # Build data
        data = {
            "carrier_id": carrier_id,
            "score": score,
            "tier": tier,
            "confidence": confidence,
            "stats": stats_summary,
            "components": score_result["components"],
            "reasons": reasons
        }
        
        # Add data quality if present (fallback)
        if "data_quality" in score_result:
            data["data_quality"] = score_result["data_quality"]
        
        # Build proofs with proper sources
        sources = []
        if source == "carrier_service":
            sources.append({
                "type": "carrier_service",
                "service": CARRIER_SERVICE_URL,
                "endpoint": CARRIER_STATS_PATH.format(carrier_id=carrier_id),
                "status": "success"
            })
        elif source == "booking_service_mvp":
            from app.tools.booking_service_client import BOOKING_SERVICE_URL
            import os
            booking_by_carrier_path = os.getenv(
                "BOOKING_BY_CARRIER_PATH",
                "/bookings?carrierId={carrier_id}&days={days}"
            )
            sources.append({
                "type": "booking_service",
                "service": BOOKING_SERVICE_URL,
                "endpoint": booking_by_carrier_path.format(carrier_id=carrier_id, days=90),
                "note": "MVP fallback - carrier service unavailable",
                "status": "fallback"
            })
        
        proofs = {
            "trace_id": trace_id,
            "sources": sources,
            "request_id": trace_id[:8],
            "user_role": user_role,
            "algorithm": "deterministic_weighted_scoring",
            "is_fallback": is_fallback
        }
        
        return {
            "message": message,
            "data": data,
            "proofs": proofs
        }

    def _handle_carrier_service_error(
        self,
        http_exception: HTTPException,
        carrier_id: str,
        trace_id: str
    ) -> Dict[str, Any]:
        """Handle HTTP exceptions from carrier service."""
        status_code = http_exception.status_code
        
        if status_code == 401:
            message = "Authentication required to access carrier scoring. Please log in."
            error_type = "Unauthorized"
        elif status_code == 403:
            message = "You don't have permission to view carrier scores."
            error_type = "Forbidden"
        elif status_code == 404:
            message = f"Carrier {carrier_id} not found in the system."
            error_type = "NotFound"
        else:
            message = "Carrier service is temporarily unavailable. Please try again later."
            error_type = "ServiceUnavailable"
        
        return self.error_response(
            message=message,
            trace_id=trace_id,
            error_type=error_type,
            status_code=status_code,
            carrier_id=carrier_id
        )

    def _return_missing_backend_error(
        self,
        carrier_id: str,
        trace_id: str,
        both_missing: bool = False
    ) -> Dict[str, Any]:
        """Return helpful error when backend endpoints are missing."""
        if both_missing:
            message = (
                f"I cannot calculate the score for carrier {carrier_id} because BOTH required backend services are not yet available.\n\n"
                "To enable carrier scoring, please implement at least one of the following:\n\n"
                f"Primary Option:\n"
                f"• Carrier Stats: GET {CARRIER_SERVICE_URL}{CARRIER_STATS_PATH}\n"
                f"  Returns: total_bookings, completed_bookings, cancelled_bookings, no_shows, late_arrivals, delays, anomalies\n\n"
                "Fallback Option:\n"
                "• Carrier Bookings: GET {{booking_service}}/bookings?carrierId={{id}}&days={{days}}\n"
                "  Returns: List of bookings with status field (used for basic scoring)"
            )
            missing_endpoints = [
                {
                    "service": "carrier_service",
                    "url": f"{CARRIER_SERVICE_URL}{CARRIER_STATS_PATH}",
                    "description": "Primary: Full carrier statistics endpoint",
                    "priority": "high"
                },
                {
                    "service": "booking_service",
                    "path": "/bookings?carrierId={id}&days={days}",
                    "description": "Fallback: Bookings filtered by carrier ID",
                    "priority": "medium"
                }
            ]
        else:
            message = (
                f"I cannot calculate the score for carrier {carrier_id} because the required backend services are not yet available.\n\n"
                "To enable carrier scoring, please implement the following backend endpoint:\n"
                f"• Carrier Stats: GET {CARRIER_SERVICE_URL}{CARRIER_STATS_PATH}\n"
                "  OR\n"
                "• Carrier Bookings: GET {{booking_service}}/bookings?carrierId={{id}}&days={{days}}"
            )
            missing_endpoints = [
                {
                    "service": "carrier_service",
                    "url": f"{CARRIER_SERVICE_URL}{CARRIER_STATS_PATH}",
                    "description": "Primary endpoint for carrier statistics"
                },
                {
                    "service": "booking_service",
                    "path": "/bookings?carrierId={id}&days={days}",
                    "description": "Alternative: Get bookings by carrier for MVP scoring"
                }
            ]
        
        data = {
            "error": "backend_not_available",
            "carrier_id": carrier_id,
            "missing_endpoints": missing_endpoints,
            "recommendation": "Implement carrier stats endpoint for accurate scoring"
        }
        
        return {
            "message": message,
            "data": data,
            "proofs": {
                "trace_id": trace_id,
                "status": "failed",
                "reason": "missing_backend_endpoints"
            }
        }
