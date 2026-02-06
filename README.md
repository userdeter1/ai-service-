# AI Service for Truck Booking Management

FastAPI-based AI service providing intelligent features for port gate management.

## Features

### Multi-Agent Chatbot
- Natural language interface for logistics queries
- Conversation history persistence
- Role-based access control (ADMIN, OPERATOR, CARRIER/DRIVER)
- Structured responses with blockchain proof

### ML-Powered Predictions
- **Traffic Peak Forecasting**: Predict traffic volumes and peak times
- **Anomaly Detection**: Identify delays and no-shows before they happen

### Smart Algorithms
- **Slot Recommendation**: Optimal time slot suggestions based on multiple criteria
- **Carrier Scoring**: Reliability scoring with explainable components

### Advanced Analytics
- **Port Stress Index**: Composite indicator of port operational stress
- **Proactive Alerts**: Operational warnings based on predictions
- **What-If Simulation**: Rule-based scenario analysis

### Blockchain Integration
- Read-only blockchain queries for audit trails
- Booking validation events
- Gate entry/exit verification
- Refusal and no-show evidence

## Architecture

### Vue d'Ensemble

```
┌──────────────────────────────────────────────────────────────────────┐
│                  CLIENT (Dashboard Frontend)                         │
└────────────────────┬────────────────────────────────┬────────────────┘
                     │                                │
                     ▼                                ▼
        ┌─────────────────────┐          ┌────────────────────────┐
        │   Mode Chatbot      │          │   Mode API Direct      │
        │  POST /api/ai/chat  │          │  GET /carriers/score   │
        │                     │          │  POST /slots/recommend │
        └──────────┬──────────┘          └──────────┬─────────────┘
                   │                                │
                   └────────────────┬───────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   AI SERVICE (FastAPI :8000)                        │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │                    API Layer                                │   │
│  │  /ai/chat │ /carriers │ /slots │ /traffic │ /anomalies     │   │
│  └──────────────────┬─────────────────────────────────────────┘   │
│                     │                                              │
│  ┌──────────────────▼────────────┐                                │
│  │  ORCHESTRATOR (Chat only)     │  ┌──────────────────────┐     │
│  │  • Intent Detector            │  │   Model Loader       │     │
│  │  • Entity Extractor           │◄─┤  • carrier_scoring   │     │
│  │  • Policy (RBAC)              │  │  • slot_recommend    │     │
│  │  • Agent Router               │  │  • traffic_forecast  │     │
│  └───────────┬───────────────────┘  └──────────────────────┘     │
│              │                                                    │
│  ┌───────────▼────────────────────────────────────────────────┐  │
│  │                 AGENTS (Spécialisés)                        │  │
│  │  • BookingAgent     • CarrierScoreAgent  • SlotAgent       │  │
│  │  • TrafficAgent     • AnomalyAgent       • AnalyticsAgent  │  │
│  └───────────┬────────────────────────────────────────────────┘  │
│              │                                                    │
│  ┌───────────▼────────────────────────────────────────────────┐  │
│  │              ALGORITHMS (Déterministes)                     │  │
│  │  • carrier_scoring.py    • slot_recommender.py             │  │
│  └───────────┬────────────────────────────────────────────────┘  │
│              │                                                    │
│  ┌───────────▼────────────────────────────────────────────────┐  │
│  │                TOOLS (HTTP Clients)                         │  │
│  │  • nest_client.py       • booking_service_client.py        │  │
│  │  • carrier_service_client.py  • slot_service_client.py     │  │
│  └───────────┬────────────────────────────────────────────────┘  │
│              │                                                    │
└──────────────┼────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────┐
│                  BACKEND SERVICES (External)                     │
│  • NestJS Backend (:3001)    - Auth, Booking CRUD                │
│  • Booking Service (:3002)   - Booking status, history           │
│  • Slot Service (:3003)      - Availability, capacity            │
│  • Carrier Service (:3004)   - Stats, profile                    │
│  • Analytics Service (:3005) - Metrics, aggregations             │
│  • Blockchain Service (:3010) - Audit trail (read-only)          │
└──────────────────────────────────────────────────────────────────┘
```

### Structure du Projet

```
ai_service/
├── ARCHITECTURE.md                      # Documentation architecture complète
├── README.md                            # Ce fichier
├── requirements.txt                    # Dépendances Python
├── .env.example                        # Template config
├── .gitignore                          # Exclusions Git
├── check_setup.py                      # Script de diagnostic
├── test_live.py                        # Test serveur live
│
└── app/                                # Code source principal
    ├── __init__.py
    ├── main.py                         # Entry point FastAPI
    │
    ├── api/                            # Endpoints REST
    │   ├── __init__.py
    │   ├── router.py                   # Agrégateur central routes
    │   ├── chat.py                     # POST /ai/chat (chatbot)
    │   ├── carriers.py                 # GET /carriers/{id}/score
    │   ├── slots.py                    # GET/POST /slots/*
    │   ├── traffic.py                  # GET /traffic/forecast
    │   ├── anomalies.py                # GET /anomalies/recent
    │   ├── analytics.py                # POST /analytics/*
    │   ├── admin.py                    # GET /admin/* (ADMIN only)
    │   └── operator.py                 # GET /operator/* (OPERATOR only)
    │
    ├── orchestrator/                   # Coordination multi-agent  
    │   ├── __init__.py
    │   ├── orchestrator.py             # execute() - Point d'entrée
    │   ├── intent_detector.py          # Détection intention (regex+keywords)
    │   ├── entity_extractor.py         # Extraction entités (booking_id, dates, etc.)
    │   ├── policy.py                   # RBAC - Vérification permissions
    │   └── response_formatter.py       # Formatage réponse finale
    │
    ├── agents/                         # Agents spécialisés
    │   ├── __init__.py
    │   ├── base_agent.py               # BaseAgent (classe abstraite)
    │   ├── registry.py                 # Mapping intent → agent
    │   ├── booking_agent.py            # Statut réservation
    │   ├── carrier_score_agent.py      # Score transporteur (fiabilité)
    │   ├── slot_agent.py               # Disponibilité + Recommandation
    │   ├── traffic_agent.py            # Prévisions trafic
    │   ├── anomaly_agent.py            # Détection anomalies
    │   ├── analytics_agent.py          # Analytics (stress index, alerts)
    │   ├── blockchain_audit_agent.py   # Audit blockchain (read-only)
    │   └── recommendation_agent.py     # Recommandations générales
    │
    ├── algorithms/                     # Algorithmes déterministes
    │   ├── __init__.py
    │   ├── carrier_scoring.py          # score_carrier() → score 0-100, tier A-D
    │   └── slot_recommender.py         # recommend_slots() → ranking + strategy
    │
    ├── models/                         # ML Models (loader + fichiers)
    │   ├── __init__.py
    │   ├── loader.py                   # get_model(), list_models()
    │   ├── traffic_model.joblib        # Modèle prévision trafic (scikit-learn)
    │   └── anomaly_model.joblib        # Modèle détection anomalies
    │
    ├── tools/                          # Clients HTTP & utilitaires
    │   ├── __init__.py
    │   ├── nest_client.py              # NestJS Backend (:3001)
    │   ├── booking_service_client.py   # Booking Service (:3002)
    │   ├── slot_service_client.py      # Slot Service (:3003)
    │   ├── carrier_service_client.py   # Carrier Service (:3004)
    │   ├── analytics_data_client.py    # Analytics Service (:3005)
    │   ├── blockchain_service_client.py# Blockchain (:3010)
    │   ├── time_tool.py                # Utilitaires temps (parsing, formatting)
    │   └── blockchain_tool.py          # Helpers blockchain (proof retrieval)
    │
    ├── analytics/                      # Analytics avancés
    │   ├── __init__.py
    │   ├── stress_index.py             # Calcul stress index portuaire
    │   ├── proactive_alerts.py         # Génération alertes proactives
    │   └── what_if_simulation.py       # Simulation scénarios what-if
    │
    ├── schemas/                        # Pydantic models (validation)
    │   ├── __init__.py
    │   ├── chat.py                     # ChatMessage, ChatRequest, ChatResponse
    │   ├── booking.py                  # BookingStatus, BookingDetails
    │   ├── carrier.py                  # CarrierScore, CarrierStats
    │   ├── slot.py                     # SlotAvailability, SlotRecommendation
    │   ├── traffic.py                  # TrafficForecast, TrafficPrediction
    │   ├── anomaly.py                  # AnomalyDetection, AnomalyAlert
    │   ├── analytics.py                # AnalyticsRequest, AnalyticsResponse
    │   ├── stress.py                   # StressIndexResponse, StressComponents
    │   └── common.py                   # BaseResponse, Proof, Error
    │
    ├── core/                           # Configuration & utilitaires centraux
    │   ├── __init__.py
    │   ├── config.py                   # Settings (env vars, URLs, timeouts)
    │   ├── logging.py                  # setup_logging(), TraceIdFilter
    │   ├── errors.py                   # AppError, ValidationError, etc.
    │   └── security.py                 # require_auth(), require_role()
    │
    ├── constants/                      # Constants
    │   ├── __init__.py
    │   ├── constants.py                # Constants générales
    │   ├── roles.py                    # ADMIN, OPERATOR, CARRIER
    │   ├── intents.py                  # BOOKING_STATUS, CARRIER_SCORE, etc.
    │   └── thresholds.py               # Seuils ML, stress levels
    │
    └── tests/                          # Tests
        ├── __init__.py
        ├── conftest.py                 # Fixtures pytest (path setup)
        ├── test_algorithms.py          # Tests carrier_scoring, slot_recommender
        ├── test_agents.py              # Tests agents (booking, carrier, slot)
        └── test_api.py                 # Tests endpoints FastAPI
```

### Flux de Traitement

#### Mode 1 : Chatbot Conversationnel

```
1. Dashboard → POST /api/ai/chat
   { "message": "Quel est le score du transporteur 123?", "user_role": "OPERATOR" }

2. Orchestrator
   ├─ Intent Detector → "carrier_score"
   ├─ Entity Extractor → { carrier_id: "123" }
   ├─ Policy Enforcer → ✓ OPERATOR autorisé
   └─ Agent Router → CarrierScoreAgent

3. CarrierScoreAgent
   ├─ HTTP GET /carriers/123/stats
   ├─ carrier_scoring.score_carrier(stats)
   └─ Return { score: 85.5, tier: "A", ... }

4. Response Formatter → Format with explanation

5. Dashboard ← { message: "...", data: {...}, proofs: {...} }
```

#### Mode 2 : API REST Direct

```
1. Dashboard → GET /api/carriers/123/score
   Headers: { Authorization, x-user-role: OPERATOR }

2. Endpoint carriers.py
   ├─ check_carrier_access() → ✓
   ├─ Model loader → carrier_scoring
   ├─ HTTP GET /carriers/123/stats
   └─ carrier_scoring.score_carrier(stats)

3. Dashboard ← { message: "...", data: {...}, proofs: {...} }
```

## API Endpoints

### Chat
- `POST /api/ai/chat` - Send message to AI assistant
- `GET /api/ai/chat/history/{conversation_id}` - Get conversation history
- `DELETE /api/ai/chat/history/{conversation_id}` - Delete conversation

### ML Features
- `POST /api/traffic/predict` - Predict traffic peaks
- `POST /api/anomalies/detect` - Detect anomalies

### Algorithms
- `POST /api/slots/recommend` - Get slot recommendations
- `POST /api/carriers/score` - Calculate carrier score

### Role-Specific
- `GET /api/admin/stress-index` - Port stress index (ADMIN only)
- `GET /api/operator/anomalies-summary` - Anomaly summary (OPERATOR only)

## Agent Routing

| Intent | Agent | Tools |
|--------|-------|-------|
| booking_status | booking_agent | booking_tool, nest_client |
| slot_availability | slot_agent | slot_tool, time_tool |
| passage_history | booking_agent | booking_tool, blockchain_tool |
| traffic_forecast | traffic_agent | traffic_model, time_tool |
| anomaly_check | anomaly_agent | anomaly_model, booking_tool |
| carrier_score | carrier_score_agent | carrier_scoring, carrier_tool |
| recommendation | recommendation_agent | slot_recommender, carrier_scoring |
| blockchain_audit | blockchain_audit_agent | blockchain_tool |

## RBAC Matrix

| Role | Chat | Traffic | Anomalies | Slots | Carriers | Stress Index | Operator Summary |
|------|------|---------|-----------|-------|----------|--------------|------------------|
| ADMIN | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| OPERATOR | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ |
| CARRIER | ✓ | ✓ | ✗ | ✓ | ✓ (own) | ✗ | ✗ |
| DRIVER | ✓ | ✓ | ✗ | ✓ | ✓ (own) | ✗ | ✗ |

## Environment Variables

Create a `.env` file:

```env
NEST_BACKEND_URL=http://localhost:3000
BLOCKCHAIN_RPC_URL=http://localhost:8545
MODEL_PATH=./app/models
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
DATABASE_URL=sqlite+aiosqlite:///./conversations.db
```

## Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the service
uvicorn app.main:app --reload --port 8000
```

## Development

```bash
# Run tests
pytest

# Format code
black app/

# Lint
flake8 app/
mypy app/
```

## Integration with NestJS Backend

The AI service communicates with the NestJS backend via HTTP:
- Authentication headers forwarded from frontend
- Real-time data queries for bookings, slots, carriers
- No direct database access (service isolation)

## Blockchain Integration

Read-only blockchain queries via:
- HTTP API endpoint (recommended for hackathon)
- Direct smart contract calls (if Web3 provider available)

Query types:
- Booking validation events
- Gate entry/exit timestamps
- Refusal records
- No-show evidence

Blockchain proof is attached to chat responses for transparency.

## Next Steps

1. Implement endpoint handlers in `api/` files
2. Build orchestrator logic and agent routing
3. Train and deploy ML models
4. Implement algorithm business logic
5. Add comprehensive tests
6. Deploy to production

---

**Built for MicroHack-3 Hackathon** 🚀
