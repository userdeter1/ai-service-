"""
Model Loader & Registry

Centralized model loading/registry for ML models with REAL->MVP fallback support.

Features:
- Lazy loading: models loaded only when first requested
- REAL mode: uses backend endpoints + ML/algorithms
- MVP mode: deterministic fallbacks when backends unavailable
- Unified interface: all models expose predict(input, context)
- Health monitoring: track loaded models, versions, modes

Usage:
    from app.models.loader import get_model
    
    model = get_model("carrier_scoring")
    result = await model.predict(
        input={"carrier_id": "123"},
        context={"auth_header": "...", "trace_id": "..."}
    )
"""

import os
import logging
from time import perf_counter
from typing import Dict, Any, Optional, List
from datetime import datetime
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

MODEL_MODE_DEFAULT = os.getenv("MODEL_MODE_DEFAULT", "real")  # "real" or "mvp"
MODEL_ARTIFACTS_DIR = os.getenv("MODEL_ARTIFACTS_DIR", "app/models/")
ENABLE_MODEL_WARMUP = os.getenv("ENABLE_MODEL_WARMUP", "false").lower() == "true"

logger.info(f"Model loader configured: mode={MODEL_MODE_DEFAULT}, warmup={ENABLE_MODEL_WARMUP}")


# ============================================================================
# Helper Functions
# ============================================================================

def _artifact_path(model_name: str, extension: str = "joblib") -> str:
    """
    Get expected artifact path for a model.
    
    Args:
        model_name: Model name (e.g., "traffic_model", "anomaly_model")
        extension: File extension (default: "joblib")
    
    Returns:
        Full path to artifact file
    """
    filename = f"{model_name}.{extension}"
    return os.path.join(MODEL_ARTIFACTS_DIR, filename)


# ============================================================================
# Model Interface
# ============================================================================

class BaseModel(ABC):
    """Base interface for all ML models."""
    
    name: str
    version: str
    mode: str  # "real" or "mvp"
    
    @abstractmethod
    async def predict(self, input: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run prediction.
        
        Args:
            input: Model-specific input data
            context: Request context (auth_header, trace_id, user_role, etc.)
        
        Returns:
            {
                "ok": bool,
                "result": {...},  # Model output
                "error": {...} if not ok,
                "proofs": {trace_id, latency_ms, mode, sources, ...}
            }
        """
        pass
    
    async def warmup(self) -> None:
        """Optional warmup/preload logic."""
        pass
    
    def close(self) -> None:
        """Optional cleanup logic."""
        pass
    
    def load_artifact(self) -> Any:
        """
        Load ML artifact (joblib, onnx, etc.).
        Override in subclass to implement actual loading.
        
        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.load_artifact() not implemented. "
            f"To load artifacts, override this method and use _artifact_path('{self.name}')."
        )


# ============================================================================
# Model Implementations
# ============================================================================

class CarrierScoringModel(BaseModel):
    """
    Carrier reliability scoring model.
    
    REAL mode: carrier_service_client.get_carrier_stats() -> score_carrier()
    MVP mode: booking service fallback with lower confidence and data_quality note
    """
    
    name = "carrier_scoring"
    version = "1.0.0"
    
    def __init__(self, mode: str = "real"):
        self.mode = mode
        self._last_loaded_at = datetime.utcnow().isoformat()
    
    async def predict(self, input: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict carrier reliability score.
        
        Input:
            - carrier_id: str (required)
            - window_days: int (optional, default 90)
        
        Context:
            - auth_header: str (optional)
            - trace_id: str (optional)
        """
        start_time = perf_counter()
        trace_id = context.get("trace_id", "unknown")
        logger.info(f"[{trace_id[:8]}] CarrierScoringModel.predict mode={self.mode}")
        
        carrier_id = input.get("carrier_id")
        if not carrier_id:
            return self._error_response(
                "carrier_id is required",
                trace_id,
                perf_counter() - start_time
            )
        
        window_days = input.get("window_days", 90)
        auth_header = context.get("auth_header")
        
        # Enforce mode
        if self.mode == "mvp":
            logger.info(f"[{trace_id[:8]}] Mode is MVP, skipping backend call")
            return await self._mvp_fallback(carrier_id, window_days, auth_header, trace_id, start_time)
        
        # Try REAL mode
        try:
            from app.tools.carrier_service_client import (
                get_carrier_stats,
                is_endpoint_missing
            )
            from app.algorithms.carrier_scoring import score_carrier
            from fastapi import HTTPException
            
            try:
                # Attempt real carrier stats
                stats = await get_carrier_stats(
                    carrier_id=carrier_id,
                    window_days=window_days,
                    auth_header=auth_header,
                    request_id=trace_id[:8]
                )
                
                # Score with algorithm
                score_result = score_carrier(stats)
                
                latency_ms = (perf_counter() - start_time) * 1000
                
                return {
                    "ok": True,
                    "result": {
                        "carrier_id": carrier_id,
                        "score": score_result["score"],
                        "tier": score_result["tier"],
                        "confidence": score_result["confidence"],
                        "components": score_result["components"],
                        "reasons": score_result["reasons"],
                        "stats_summary": score_result["stats_summary"]
                    },
                    "proofs": {
                        "trace_id": trace_id,
                        "model": self.name,
                        "version": self.version,
                        "mode": "real",
                        "latency_ms": round(latency_ms, 2),
                        "sources": ["carrier_service"]
                    }
                }
                
            except HTTPException as e:
                # Check if endpoint missing -> fallback to MVP
                if is_endpoint_missing(e):
                    logger.warning(f"[{trace_id[:8]}] Carrier endpoint missing, falling back to MVP")
                    return await self._mvp_fallback(carrier_id, window_days, auth_header, trace_id, start_time)
                else:
                    # Other HTTP error (auth, forbidden, etc.) - safe error
                    logger.error(f"[{trace_id[:8]}] Carrier service HTTP error {e.status_code}: {e.detail}")
                    return self._error_response(
                        "Unable to retrieve carrier data",
                        trace_id,
                        perf_counter() - start_time,
                        error_type="ServiceError"
                    )
                    
        except Exception as e:
            logger.exception(f"[{trace_id[:8]}] CarrierScoringModel error: {e}")
            return self._error_response(
                "Model prediction failed",
                trace_id,
                perf_counter() - start_time
            )
    
    async def _mvp_fallback(
        self,
        carrier_id: str,
        window_days: int,
        auth_header: Optional[str],
        trace_id: str,
        start_time: float
    ) -> Dict[str, Any]:
        """MVP fallback using booking service."""
        try:
            from app.tools.booking_service_client import (
                BOOKING_SERVICE_URL,
                get_client as get_booking_client
            )
            from app.algorithms.carrier_scoring import score_carrier
            import httpx
            
            # Try booking-by-carrier endpoint
            booking_by_carrier_path = os.getenv(
                "BOOKING_BY_CARRIER_PATH",
                "/bookings?carrierId={carrier_id}&days={days}"
            )
            url = f"{BOOKING_SERVICE_URL}{booking_by_carrier_path}".format(
                carrier_id=carrier_id,
                days=window_days
            )
            
            headers = {
                "Content-Type": "application/json",
                "x-request-id": trace_id[:8]  # Propagate request ID
            }
            if auth_header:
                headers["Authorization"] = auth_header
            
            client = get_booking_client()
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            bookings_data = response.json()
            
            # Extract bookings
            if isinstance(bookings_data, dict):
                bookings = bookings_data.get("data") or bookings_data.get("bookings") or []
            elif isinstance(bookings_data, list):
                bookings = bookings_data
            else:
                bookings = []
            
            # Compute minimal stats
            stats = self._compute_stats_from_bookings(bookings)
            
            if stats["total_bookings"] == 0:
                return self._error_response(
                    f"No booking history available for carrier",
                    trace_id,
                    perf_counter() - start_time,
                    error_type="InsufficientData"
                )
            
            # Score with algorithm (NO CAPPING)
            score_result = score_carrier(stats)
            
            # MVP honesty: Lower confidence and add data_quality note
            # Do NOT cap score to maintain tier consistency
            original_confidence = score_result["confidence"]
            score_result["confidence"] = min(0.6, score_result["confidence"])
            
            latency_ms = (perf_counter() - start_time) * 1000
            
            logger.info(
                f"[{trace_id[:8]}] MVP fallback score: {score_result['score']:.1f}, "
                f"tier: {score_result['tier']}, "
                f"confidence: {score_result['confidence']:.2f} (capped from {original_confidence:.2f})"
            )
            
            return {
                "ok": True,
                "result": {
                    "carrier_id": carrier_id,
                    "score": score_result["score"],
                    "tier": score_result["tier"],
                    "confidence": score_result["confidence"],
                    "components": score_result["components"],
                    "reasons": score_result["reasons"],
                    "stats_summary": score_result["stats_summary"],
                    "data_quality": stats.get("data_quality", {}),
                    "mvp_note": "Score computed from limited booking data - confidence reduced to reflect data quality"
                },
                "proofs": {
                    "trace_id": trace_id,
                    "model": self.name,
                    "version": self.version,
                    "mode": "mvp",
                    "latency_ms": round(latency_ms, 2),
                    "sources": ["booking_service_fallback"]
                }
            }
            
        except httpx.HTTPStatusError as e:
            logger.warning(f"[{trace_id[:8]}] MVP fallback HTTP error {e.response.status_code}")
            return self._error_response(
                "Carrier scoring unavailable",
                trace_id,
                perf_counter() - start_time,
                error_type="BackendUnavailable"
            )
        except Exception as e:
            logger.warning(f"[{trace_id[:8]}] MVP fallback failed: {type(e).__name__}")
            return self._error_response(
                "Carrier scoring unavailable",
                trace_id,
                perf_counter() - start_time,
                error_type="BackendUnavailable"
            )
    
    def _compute_stats_from_bookings(self, bookings: List[Dict]) -> Dict[str, Any]:
        """Compute minimal stats from booking list."""
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
                    "missing_metrics": ["no_shows", "late_arrivals", "delays", "anomalies"],
                    "source": "booking_service_fallback"
                }
            }
        
        completed = sum(1 for b in bookings if str(b.get("status", "")).lower() in ("completed", "consumed"))
        cancelled = sum(1 for b in bookings if str(b.get("status", "")).lower() in ("cancelled", "canceled"))
        
        return {
            "total_bookings": total,
            "completed_bookings": completed,
            "cancelled_bookings": cancelled,
            "no_shows": 0,
            "late_arrivals": 0,
            "avg_delay_minutes": 0.0,
            "avg_dwell_minutes": 0.0,
            "anomaly_count": 0,
            "last_activity_at": "N/A",
            "data_quality": {
                "missing_metrics": ["no_shows", "late_arrivals", "delays", "anomalies"],
                "source": "booking_service_fallback"
            }
        }
    
    def _error_response(
        self,
        message: str,
        trace_id: str,
        elapsed: float,
        error_type: str = "ModelError"
    ) -> Dict[str, Any]:
        """Build error response."""
        return {
            "ok": False,
            "error": {
                "type": error_type,
                "message": message
            },
            "proofs": {
                "trace_id": trace_id,
                "model": self.name,
                "version": self.version,
                "mode": self.mode,
                "latency_ms": round(elapsed * 1000, 2),
                "sources": []
            }
        }


class SlotRecommendationModel(BaseModel):
    """
    Slot recommendation model.
    
    REAL mode: slot_service_client.get_availability() -> recommend_slots()
    MVP mode: error or rank provided candidates locally
    """
    
    name = "slot_recommendation"
    version = "1.0.0"
    
    def __init__(self, mode: str = "real"):
        self.mode = mode
        self._last_loaded_at = datetime.utcnow().isoformat()
    
    async def predict(self, input: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recommend optimal slots.
        
        Input:
            - terminal: str (required)
            - date: str YYYY-MM-DD (required)
            - gate: str (optional)
            - carrier_id: str (optional, for carrier-aware ranking)
            - requested_time: str (optional, for time-distance scoring)
            - candidates: List[dict] (optional, for MVP mode local ranking)
        
        Context:
            - auth_header: str
            - trace_id: str
        """
        start_time = perf_counter()
        trace_id = context.get("trace_id", "unknown")
        logger.info(f"[{trace_id[:8]}] SlotRecommendationModel.predict mode={self.mode}")
        
        terminal = input.get("terminal")
        date_str = input.get("date")
        
        if not terminal or not date_str:
            return self._error_response(
                "terminal and date are required",
                trace_id,
                perf_counter() - start_time
            )
        
        gate = input.get("gate")
        carrier_id = input.get("carrier_id")
        requested_time = input.get("requested_time")
        auth_header = context.get("auth_header")
        
        # Enforce mode
        if self.mode == "mvp":
            logger.info(f"[{trace_id[:8]}] Mode is MVP, skipping backend call")
            return self._mvp_fallback(input, trace_id, start_time)
        
        # Try REAL mode
        try:
            from app.tools.slot_service_client import (
                get_availability,
                is_endpoint_missing
            )
            from app.algorithms.slot_recommender import recommend_slots
            from fastapi import HTTPException
            
            try:
                # Fetch availability
                slots = await get_availability(
                    terminal=terminal,
                    date=date_str,
                    gate=gate,
                    auth_header=auth_header,
                    request_id=trace_id[:8]
                )
                
                # Get carrier score if carrier_id provided
                carrier_score = None
                if carrier_id:
                    try:
                        carrier_model = get_model("carrier_scoring")
                        carrier_result = await carrier_model.predict(
                            input={"carrier_id": carrier_id},
                            context=context
                        )
                        if carrier_result.get("ok"):
                            carrier_score = carrier_result["result"].get("score")
                    except Exception as e:
                        logger.warning(f"[{trace_id[:8]}] Could not get carrier score: {type(e).__name__}")
                
                # Run recommender
                requested = {
                    "start": requested_time or f"{date_str} 09:00:00",
                    "terminal": terminal,
                    "gate": gate
                }
                
                reco_result = recommend_slots(
                    requested=requested,
                    candidates=slots,
                    carrier_score=carrier_score
                )
                
                latency_ms = (perf_counter() - start_time) * 1000
                
                return {
                    "ok": True,
                    "result": {
                        "terminal": terminal,
                        "date": date_str,
                        "recommended": reco_result["recommended"],
                        "strategy": reco_result["strategy"],
                        "reasons": reco_result["reasons"],
                        "total_candidates": len(slots)
                    },
                    "proofs": {
                        "trace_id": trace_id,
                        "model": self.name,
                        "version": self.version,
                        "mode": "real",
                        "latency_ms": round(latency_ms, 2),
                        "sources": ["slot_service"]
                    }
                }
                
            except HTTPException as e:
                if is_endpoint_missing(e):
                    logger.warning(f"[{trace_id[:8]}] Slot endpoint missing, checking MVP mode")
                    return self._mvp_fallback(input, trace_id, start_time)
                else:
                    logger.error(f"[{trace_id[:8]}] Slot service HTTP error {e.status_code}: {e.detail}")
                    return self._error_response(
                        "Unable to retrieve slot availability",
                        trace_id,
                        perf_counter() - start_time,
                        error_type="ServiceError"
                    )
                    
        except Exception as e:
            logger.exception(f"[{trace_id[:8]}] SlotRecommendationModel error: {e}")
            return self._error_response(
                "Model prediction failed",
                trace_id,
                perf_counter() - start_time
            )
    
    def _mvp_fallback(self, input: Dict[str, Any], trace_id: str, start_time: float) -> Dict[str, Any]:
        """MVP mode: rank provided candidates or return error."""
        candidates = input.get("candidates")
        
        if candidates:
            # Local ranking of provided candidates
            try:
                from app.algorithms.slot_recommender import recommend_slots
                
                terminal = input.get("terminal")
                date_str = input.get("date")
                gate = input.get("gate")
                requested_time = input.get("requested_time")
                
                requested = {
                    "start": requested_time or f"{date_str} 09:00:00",
                    "terminal": terminal,
                    "gate": gate
                }
                
                # Note: can't get carrier score in MVP without backend
                reco_result = recommend_slots(
                    requested=requested,
                    candidates=candidates,
                    carrier_score=None
                )
                
                latency_ms = (perf_counter() - start_time) * 1000
                
                return {
                    "ok": True,
                    "result": {
                        "terminal": terminal,
                        "date": date_str,
                        "recommended": reco_result["recommended"],
                        "strategy": reco_result["strategy"],
                        "reasons": reco_result["reasons"],
                        "total_candidates": len(candidates)
                    },
                    "proofs": {
                        "trace_id": trace_id,
                        "model": self.name,
                        "version": self.version,
                        "mode": "mvp",
                        "latency_ms": round(latency_ms, 2),
                        "sources": ["local_candidates"]
                    }
                }
            except Exception as e:
                logger.exception(f"[{trace_id[:8]}] MVP ranking failed: {e}")
                return self._error_response(
                    "Slot ranking failed",
                    trace_id,
                    perf_counter() - start_time
                )
        else:
            # No candidates provided, can't help
            return self._error_response(
                "Slot availability service unavailable",
                trace_id,
                perf_counter() - start_time,
                error_type="BackendUnavailable"
            )
    
    def _error_response(
        self,
        message: str,
        trace_id: str,
        elapsed: float,
        error_type: str = "ModelError"
    ) -> Dict[str, Any]:
        """Build error response."""
        return {
            "ok": False,
            "error": {
                "type": error_type,
                "message": message
            },
            "proofs": {
                "trace_id": trace_id,
                "model": self.name,
                "version": self.version,
                "mode": self.mode,
                "latency_ms": round(elapsed * 1000, 2),
                "sources": []
            }
        }


class DriverNoShowRiskModel(BaseModel):
    """
    Driver no-show risk prediction model.
    
    REAL mode: future backend endpoint for driver stats
    MVP mode: deterministic heuristics based on carrier score + booking status
    """
    
    name = "driver_noshow_risk"
    version = "1.0.0"
    
    def __init__(self, mode: str = "real"):
        self.mode = mode
        self._last_loaded_at = datetime.utcnow().isoformat()
    
    async def predict(self, input: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict driver no-show risk.
        
        Input:
            - booking_ref: str (optional)
            - carrier_id: str (optional)
            - driver_id: str (optional, future)
            - booking_status: str (optional)
        
        Context:
            - auth_header: str
            - trace_id: str
        """
        start_time = perf_counter()
        trace_id = context.get("trace_id", "unknown")
        logger.info(f"[{trace_id[:8]}] DriverNoShowRiskModel.predict mode={self.mode}")
        
        # Enforce mode
        if self.mode == "mvp":
            logger.info(f"[{trace_id[:8]}] Mode is MVP, using heuristics")
            return await self._mvp_heuristic(input, context, trace_id, start_time)
        
        # Try REAL mode (future endpoint)
        driver_stats_url = os.getenv("DRIVER_STATS_URL")
        driver_stats_path = os.getenv("DRIVER_STATS_PATH", "/drivers/{driver_id}/stats")
        
        if driver_stats_url:
            # Future: call driver stats endpoint
            logger.info(f"[{trace_id[:8]}] DRIVER_STATS_URL configured but endpoint not implemented yet")
        
        # Fall back to MVP mode
        logger.info(f"[{trace_id[:8]}] Driver stats endpoint not available, using MVP heuristics")
        return await self._mvp_heuristic(input, context, trace_id, start_time)
    
    async def _mvp_heuristic(
        self,
        input: Dict[str, Any],
        context: Dict[str, Any],
        trace_id: str,
        start_time: float
    ) -> Dict[str, Any]:
        """MVP heuristic risk calculation."""
        carrier_id = input.get("carrier_id")
        booking_status = input.get("booking_status", "").lower()
        
        # Base risk
        risk_score = 0.3  # 30% baseline
        risk_factors = []
        
        # Factor 1: Carrier score
        if carrier_id:
            try:
                carrier_model = get_model("carrier_scoring")
                carrier_result = await carrier_model.predict(
                    input={"carrier_id": carrier_id},
                    context=context
                )
                
                if carrier_result.get("ok"):
                    carrier_score = carrier_result["result"].get("score", 70)
                    
                    if carrier_score < 50:
                        risk_score += 0.3
                        risk_factors.append("Low carrier reliability score (<50)")
                    elif carrier_score < 70:
                        risk_score += 0.15
                        risk_factors.append("Moderate carrier reliability score (50-70)")
                    else:
                        risk_score -= 0.1
                        risk_factors.append("High carrier reliability score (70+)")
            except Exception as e:
                logger.warning(f"[{trace_id[:8]}] Could not get carrier score: {type(e).__name__}")
        
        # Factor 2: Booking status
        if booking_status in ("cancelled", "canceled"):
            risk_score += 0.4
            risk_factors.append("Booking cancelled - high no-show risk")
        elif booking_status == "pending":
            risk_score += 0.1
            risk_factors.append("Booking pending - slight risk increase")
        elif booking_status in ("confirmed", "completed"):
            risk_score -= 0.1
            risk_factors.append("Booking confirmed/completed - lower risk")
        
        # Clamp to 0-1
        risk_score = max(0.0, min(1.0, risk_score))
        
        # Risk level
        if risk_score < 0.3:
            risk_level = "low"
        elif risk_score < 0.6:
            risk_level = "medium"
        else:
            risk_level = "high"
        
        latency_ms = (perf_counter() - start_time) * 1000
        
        return {
            "ok": True,
            "result": {
                "risk_score": round(risk_score, 3),
                "risk_level": risk_level,
                "risk_factors": risk_factors,
                "explanation": f"Deterministic risk based on {len(risk_factors)} factors"
            },
            "proofs": {
                "trace_id": trace_id,
                "model": self.name,
                "version": self.version,
                "mode": "mvp",
                "latency_ms": round(latency_ms, 2),
                "sources": ["heuristic"]
            }
        }


# ============================================================================
# Model Registry
# ============================================================================

class ModelRegistry:
    """Centralized registry for lazy-loaded models."""
    
    def __init__(self):
        self._models: Dict[str, BaseModel] = {}
        self._model_classes = {
            "carrier_scoring": CarrierScoringModel,
            "slot_recommendation": SlotRecommendationModel,
            "driver_noshow_risk": DriverNoShowRiskModel,
        }
        
        # Artifact metadata (expected paths for future ML artifacts)
        self._artifact_metadata = {
            "traffic_model": {"path": _artifact_path("traffic_model"), "type": "joblib"},
            "anomaly_model": {"path": _artifact_path("anomaly_model"), "type": "joblib"},
        }
    
    def get_model(self, name: str) -> BaseModel:
        """
        Get model by name, lazy-loading if not already loaded.
        
        Args:
            name: Model name (e.g., "carrier_scoring")
        
        Returns:
            Model instance
        
        Raises:
            ValueError: If model name not recognized
        """
        if name in self._models:
            return self._models[name]
        
        if name not in self._model_classes:
            raise ValueError(f"Unknown model: {name}. Available: {list(self._model_classes.keys())}")
        
        # Lazy load
        model_class = self._model_classes[name]
        model = model_class(mode=MODEL_MODE_DEFAULT)
        
        logger.info(f"Loaded model: {name} (mode={model.mode}, version={model.version})")
        
        # Optional warmup
        if ENABLE_MODEL_WARMUP:
            try:
                import asyncio
                asyncio.create_task(model.warmup())
            except Exception as e:
                logger.warning(f"Model warmup failed for {name}: {e}")
        
        self._models[name] = model
        return model
    
    def list_models(self) -> Dict[str, Dict[str, Any]]:
        """List all available models and their status."""
        result = {}
        
        # Active models
        for name in self._model_classes:
            result[name] = {
                "available": True,
                "loaded": name in self._models,
                "class": self._model_classes[name].__name__,
                "version": self._models[name].version if name in self._models else "N/A",
                "mode": self._models[name].mode if name in self._models else MODEL_MODE_DEFAULT,
                "artifact_expected_path": None  # These don't use artifacts yet
            }
        
        # Future ML artifact models
        for name, metadata in self._artifact_metadata.items():
            result[name] = {
                "available": False,
                "loaded": False,
                "class": "FutureMLModel",
                "version": "N/A",
                "mode": "N/A",
                "artifact_expected_path": metadata["path"],
                "artifact_type": metadata["type"],
                "artifact_exists": os.path.exists(metadata["path"])
            }
        
        return result
    
    def reload_model(self, name: str) -> BaseModel:
        """
        Reload a model (close and re-initialize).
        
        Args:
            name: Model name
        
        Returns:
            New model instance
        """
        if name in self._models:
            old_model = self._models[name]
            try:
                old_model.close()
            except Exception as e:
                logger.warning(f"Error closing model {name}: {e}")
            
            del self._models[name]
        
        return self.get_model(name)
    
    def healthcheck(self) -> Dict[str, Any]:
        """
        Get health status of all loaded models.
        
        Returns:
            {
                "loaded_models": {...},
                "available_models": [...],
                "config": {...}
            }
        """
        return {
            "loaded_models": {
                name: {
                    "name": model.name,
                    "version": model.version,
                    "mode": model.mode,
                    "last_loaded_at": getattr(model, "_last_loaded_at", "N/A")
                }
                for name, model in self._models.items()
            },
            "available_models": list(self._model_classes.keys()),
            "artifact_models": list(self._artifact_metadata.keys()),
            "config": {
                "default_mode": MODEL_MODE_DEFAULT,
                "artifacts_dir": MODEL_ARTIFACTS_DIR,
                "warmup_enabled": ENABLE_MODEL_WARMUP
            }
        }
    
    def close_all(self) -> None:
        """Close all loaded models."""
        for name, model in self._models.items():
            try:
                model.close()
                logger.info(f"Closed model: {name}")
            except Exception as e:
                logger.error(f"Error closing model {name}: {e}")
        
        self._models.clear()


# ============================================================================
# Module-level singleton & convenience functions
# ============================================================================

_registry = ModelRegistry()


def get_model(name: str) -> BaseModel:
    """
    Get model by name (module-level convenience).
    
    Usage:
        from app.models.loader import get_model
        model = get_model("carrier_scoring")
        result = await model.predict(input={...}, context={...})
    """
    return _registry.get_model(name)


def list_models() -> Dict[str, Dict[str, Any]]:
    """List all available models."""
    return _registry.list_models()


def reload_model(name: str) -> BaseModel:
    """Reload a specific model."""
    return _registry.reload_model(name)


def models_health() -> Dict[str, Any]:
    """Get health status of all models."""
    return _registry.healthcheck()


def close_all_models() -> None:
    """Close all loaded models (call during shutdown)."""
    _registry.close_all()
