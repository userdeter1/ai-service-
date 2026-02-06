"""
Pydantic Schemas Package

Provides typed request/response models for FastAPI AI service endpoints.
All schemas match existing agent/model/service client response structures.

Schema Conventions:
- BaseAgent responses: {message: str, data: dict, proofs: Proofs}
- Model outputs: {ok: bool, result/error: dict, proofs: Proofs}
- Service clients: Normalized dicts with specific keys per service

Export Groups:
- Base: Proofs, AgentResponse, ErrorResponse
- Chat: ChatRequest, ChatResponse
- Carrier: CarrierScore schemas
- Slot: SlotRecommendation schemas
- Analytics: Stress, Alerts, WhatIf schemas
- Traffic: TrafficForecast schemas
- Anomaly: AnomalyDetection schemas
- Blockchain: BlockchainAudit schemas
"""

# Base schemas
from app.schemas.base import (
    Proofs,
    AgentResponse,
    ErrorResponse,
    ValidationErrorResponse
)

# Chat schemas
from app.schemas.chat import (
    ChatRequest,
    ChatResponse
)

# Carrier scoring schemas
from app.schemas.carrier_score import (
    CarrierStatsSummary,
    CarrierScoreComponents,
    CarrierScoreResult,
    CarrierScoreResponse
)

# Slot/recommendation schemas
from app.schemas.recommend import (
    SlotItem,
    SlotRecommendationResult,
    SlotAvailabilityResponse,
    SlotRecommendationResponse
)

# Analytics/stress schemas
from app.schemas.stress import (
    StressDrivers,
    StressIndexResult,
    StressIndexResponse,
    AlertItem,
    AlertsResponse,
    WhatIfScenario,
    WhatIfResult,
    WhatIfResponse
)

# Traffic schemas
from app.schemas.traffic import (
    TrafficForecastResult,
    TrafficResponse
)

# Anomaly schemas
from app.schemas.anomalies import (
    AnomalyItem,
    AnomaliesResponse
)

# Blockchain schemas
from app.schemas.blockchain import (
    BlockchainAuditRequest,
    BlockchainAuditResult,
    BlockchainAuditResponse
)

__all__ = [
    # Base
    "Proofs",
    "AgentResponse",
    "ErrorResponse",
    "ValidationErrorResponse",
    # Chat
    "ChatRequest",
    "ChatResponse",
    # Carrier
    "CarrierStatsSummary",
    "CarrierScoreComponents",
    "CarrierScoreResult",
    "CarrierScoreResponse",
    # Slot/Recommend
    "SlotItem",
    "SlotRecommendationResult",
    "SlotAvailabilityResponse",
    "SlotRecommendationResponse",
    # Analytics/Stress
    "StressDrivers",
    "StressIndexResult",
    "StressIndexResponse",
    "AlertItem",
    "AlertsResponse",
    "WhatIfScenario",
    "WhatIfResult",
    "WhatIfResponse",
    # Traffic
    "TrafficForecastResult",
    "TrafficResponse",
    # Anomaly
    "AnomalyItem",
    "AnomaliesResponse",
    # Blockchain
    "BlockchainAuditRequest",
    "BlockchainAuditResult",
    "BlockchainAuditResponse"
]
