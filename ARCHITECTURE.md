# Architecture du Service IA - Smart Port

> **Guide d'Implémentation Complet pour l'Équipe**

---

## 📋 Table des Matières

1. [Vue d'Ensemble](#vue-densemble)
2. [Architecture Globale](#architecture-globale)
3. [Flux de Traitement](#flux-de-traitement)
4. [Composants Principaux](#composants-principaux)
5. [Endpoints API](#endpoints-api)
6. [Guide d'Extension](#guide-dextension)
7. [Configuration & Déploiement](#configuration--déploiement)
8. [Tests & Validation](#tests--validation)

---

## 🎯 Vue d'Ensemble

Le **Service IA** est un microservice FastAPI Python qui fournit des capacités d'intelligence artificielle pour le Smart Port :

### Fonctionnalités Principales

- **Scoring de Transporteurs** : Évalue la fiabilité (Score 0-100, Tiers A-D)
- **Recommandation de Créneaux** : Suggère les meilleurs slots selon disponibilité et carrier
- **Détection d'Anomalies** : Identifie comportements inhabituels (no-shows, retards)
- **Prévisions de Trafic** : Prévoit la charge par terminal
- **Analytics** : Calcul du stress index, what-if scenarios
- **Blockchain Audit** : Traçabilité et intégrité des données
- **Chatbot Conversationnel** : Interface NLP pour les requêtes en langage naturel

### Technologies

- **Framework** : FastAPI (Python 3.9+)
- **HTTP Client** : httpx (async avec connection pooling)
- **Validation** : Pydantic V2
- **Logging** : Standard library avec trace_id propagation
- **ML/Analytics** : Algorithmes déterministes (pas de TensorFlow/PyTorch requis pour MVP)

---

## 🏗️ Architecture Globale

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT                                   │
│              (Dashboard Frontend / External API)                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API LAYER (FastAPI)                           │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────────┐  │
│  │ /ai/chat │ /carriers│  /slots  │ /traffic │ /anomalies   │  │
│  │          │  /score  │/recommend│/forecast │   /recent    │  │
│  └──────────┴──────────┴──────────┴──────────┴──────────────┘  │
│         ▲ Authentication & RBAC (x-user-role, Authorization)    │
└─────────┴───────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│               ORCHESTRATOR (Chat Mode uniquement)                │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Intent Detector│→│Entity Extractor│→│ Policy Enforcer  │   │
│  │ (patterns NLP) │  │ (regex extract)│  │   (RBAC check)   │   │
│  └────────────────┘  └──────────────┘  └──────────────────┘   │
│                            ▼                                     │
│                    ┌──────────────┐                             │
│                    │ Agent Router │                             │
│                    └──────────────┘                             │
└─────────────────────────┬───────────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┬─────────────────┐
          ▼                               ▼                 ▼
┌──────────────────┐        ┌──────────────────┐   ┌──────────────┐
│  AGENTS          │        │  ALGORITHMS      │   │    TOOLS     │
│                  │        │                  │   │              │
│ • BookingAgent   │───────▶│ • carrier_       │   │ • HTTP       │
│ • CarrierScore   │        │   scoring.py     │   │   Clients    │
│   Agent          │        │ • slot_          │   │ • Time Utils │
│ • SlotAgent      │───────▶│   recommender.py │   │ • Blockchain │
│ • AnalyticsAgent │        │                  │   │   Tool       │
│ • TrafficAgent   │        └──────────────────┘   └──────────────┘
│ • AnomalyAgent   │                 ▲                     │
└──────────────────┘                 │                     │
          │                          │                     │
          └──────────────────────────┴─────────────────────┘
                                     │
                                     ▼
          ┌──────────────────────────────────────────────────┐
          │          BACKEND SERVICES (External)             │
          │  • NestJS Backend (:3001)                        │
          │  • Booking Service (:3002)                       │
          │  • Slot Service (:3003)                          │
          │  • Carrier Service (:3004)                       │
          │  • Analytics Service (:3005)                     │
          │  • Blockchain Service (:3010)                    │
          └──────────────────────────────────────────────────┘
```

---

## 🔄 Flux de Traitement

### Mode 1 : Chatbot Conversationnel

```
1. Client → POST /api/ai/chat
   Body: { message: "Score du transporteur 123?", user_role: "OPERATOR" }

2. API Router → Orchestrator.execute()

3. Intent Detector
   ├─ Analyse le message avec patterns regex
   └─ Résultat: "carrier_score"

4. Entity Extractor
   ├─ Extrait les entités (carrier_id: "123")
   └─ Résultat: { carrier_id: "123" }

5. Policy Enforcer
   ├─ Vérifie RBAC (OPERATOR peut voir carrier_score)
   └─ ✓ Autorisé

6. Agent Router
   ├─ Routing intent → agent
   └─ Sélection: CarrierScoreAgent

7. CarrierScoreAgent.execute()
   ├─ HTTP GET /carriers/123/stats
   ├─ Appel algorithme: carrier_scoring.score_carrier(stats)
   └─ Résultat: { score: 85.5, tier: "A", ... }

8. Response Formatter
   └─ Format: { message: "...", data: {...}, proofs: {...} }

9. Client ← Réponse JSON structurée
```

### Mode 2 : API REST Directe

```
1. Dashboard → GET /api/carriers/123/score
   Headers: { Authorization, x-user-role: OPERATOR }

2. API Endpoint (carriers.py)
   ├─ check_carrier_access(request, "123")
   └─ ✓ OPERATOR autorisé

3. Model Loader
   └─ get_model("carrier_scoring")

4. Model.predict()
   ├─ HTTP GET /carriers/123/stats
   ├─ carrier_scoring.score_carrier(stats)
   └─ Résultat: { score: 85.5, tier: "A", ... }

5. Dashboard ← Réponse JSON directe
```

---

## 🧩 Composants Principaux

### 1. **API Layer** (`app/api/`)

Expose les endpoints REST. Chaque module gère un domaine spécifique.

#### Structure

```
app/api/
├── __init__.py
├── router.py           # Agrégateur central de tous les routers
├── chat.py             # POST /ai/chat (chatbot)
├── carriers.py         # GET /carriers/{id}/score, /stats
├── slots.py            # GET /availability, POST /recommend
├── traffic.py          # GET /forecast
├── anomalies.py        # GET /recent
├── analytics.py        # POST /stress, /what-if
├── blockchain.py       # POST /audit
├── admin.py            # Endpoints admin
└── operator.py         # Endpoints opérateur
```

#### Responsabilités

- **Validation des inputs** (Pydantic schemas)
- **Extraction des headers** (auth, role, trace_id, carrier_id)
- **Vérification RBAC** (require_operator_or_admin, check_carrier_access)
- **Appel des Models/Agents**
- **Formatage des réponses** (standard_response)

#### Exemple : Endpoint Carrier Score

```python
# app/api/carriers.py
@router.get("/carriers/{carrier_id}/score")
async def get_carrier_score(carrier_id: str, request: Request):
    # 1. Check RBAC
    check_carrier_access(request, carrier_id)
    
    # 2. Get trace_id, auth
    trace_id = get_trace_id(request)
    auth_header = get_auth_header(request)
    
    # 3. Load model
    model = get_model("carrier_scoring")
    
    # 4. Predict
    result = await model.predict(
        input={"carrier_id": carrier_id},
        context={"auth_header": auth_header, "trace_id": trace_id}
    )
    
    # 5. Return
    return standard_response(
        message=f"Score: {result['score']}/100 (Tier {result['tier']})",
        data=result,
        trace_id=trace_id
    )
```

---

### 2. **Orchestrator** (`app/orchestrator/`)

Gère le flux conversationnel (chatbot uniquement).

#### Composants

```
app/orchestrator/
├── __init__.py
├── orchestrator.py      # execute() - Point d'entrée principal
├── intent_detector.py   # detect_intent(message) → intent string
├── entity_extractor.py  # extract_entities(message, intent) → dict
├── policy.py            # enforce_policy(intent, role, entities)
└── response_formatter.py# format_response(agent_result, context)
```

#### Flux

```python
# orchestrator.py
async def execute(context: dict) -> dict:
    message = context["message"]
    user_role = context["user_role"]
    
    # 1. Détecter l'intention
    intent = detect_intent(message)
    
    # 2. Extraire les entités
    entities = extract_entities(message, intent)
    
    # 3. Vérifier la politique RBAC
    enforce_policy(intent, user_role, entities)
    
    # 4. Router vers l'agent approprié
    agent = get_agent_for_intent(intent)
    
    # 5. Exécuter l'agent
    result = await agent.execute({**context, **entities, "intent": intent})
    
    # 6. Formater la réponse
    return format_response(result, context)
```

#### Intent Detection

**Patterns supportés** (FR/EN) :

```python
INTENT_PATTERNS = {
    "booking_status": [
        r"statut.*(?:réservation|booking).*(?P<ref>[A-Z0-9\-]+)",
        r"(?P<ref>REF[0-9]+|BK\-[0-9]+).*(?:statut|status)"
    ],
    "carrier_score": [
        r"score.*(?:transporteur|carrier).*(?P<carrier_id>\d+)",
        r"fiabilité.*(?P<carrier_id>\d+)"
    ],
    "slot_availability": [
        r"(?:créneaux|slots).*disponibles?.*terminal\s*(?P<terminal>[A-Z])",
        r"availability.*terminal\s*(?P<terminal>[A-Z])"
    ]
}
```

---

### 3. **Agents** (`app/agents/`)

Agents spécialisés pour chaque domaine métier.

#### Structure

```
app/agents/
├── __init__.py
├── base_agent.py           # BaseAgent (classe abstraite)
├── booking_agent.py        # Statut réservation
├── carrier_score_agent.py  # Score transporteur
├── slot_agent.py           # Disponibilité/Recommandation slots
├── analytics_agent.py      # Stress index, what-if
├── traffic_agent.py        # Prévisions trafic
├── anomaly_agent.py        # Détection anomalies
├── blockchain_audit_agent.py # Audit blockchain
└── registry.py             # Mapping intent → agent
```

#### Base Agent

```python
# app/agents/base_agent.py
class BaseAgent:
    async def execute(self, context: dict) -> dict:
        """
        Exécute la logique métier de l'agent.
        
        Args:
            context: {
                "message": str,
                "user_id": int,
                "user_role": str,
                "entities": dict,
                "intent": str,
                "auth_header": str,
                "trace_id": str
            }
        
        Returns:
            {
                "message": str,      # Texte descriptif
                "data": dict,        # Données structurées
                "proofs": dict       # Traçabilité (trace_id, timestamps, etc.)
            }
        """
        raise NotImplementedError
```

#### Exemple : CarrierScoreAgent

```python
# app/agents/carrier_score_agent.py
class CarrierScoreAgent(BaseAgent):
    async def execute(self, context: dict) -> dict:
        carrier_id = context["entities"].get("carrier_id")
        auth_header = context.get("auth_header")
        
        # 1. Fetcher les stats (avec fallback REAL→MVP)
        try:
            stats = await carrier_service_client.get_carrier_stats(
                carrier_id, auth_header
            )
        except HTTPStatusError as e:
            if e.response.status_code in (404, 405, 501):
                # Fallback: utiliser booking_service
                stats = await booking_service_client.get_carrier_bookings(
                    carrier_id, auth_header
                )
        
        # 2. Calculer le score (algorithme déterministe)
        from app.algorithms.carrier_scoring import score_carrier
        result = score_carrier(stats)
        
        # 3. Formater
        return {
            "message": f"Transporteur {carrier_id}: {result['score']}/100 (Tier {result['tier']})",
            "data": {
                "carrier_id": carrier_id,
                **result
            },
            "proofs": {
                "trace_id": context["trace_id"],
                "data_quality": "real" if not fallback else "mvp"
            }
        }
```

---

### 4. **Algorithms** (`app/algorithms/`)

Algorithmes déterministes pour le scoring et la recommandation.

#### Structure

```
app/algorithms/
├── __init__.py
├── carrier_scoring.py      # score_carrier(stats) → score, tier, components
└── slot_recommender.py     # recommend_slots(requested, candidates, carrier_score)
```

#### Carrier Scoring

**Formule pondérée** :

```
Score Final = 
    Completion Rate × 30% +
    On-Time Performance × 25% +
    No-Show Penalty × 20% +
    Anomaly Penalty × 15% +
    Dwell Efficiency × 10%
```

**Tiers** :
- **A** : ≥85 (Excellent)
- **B** : ≥70 (Bon)
- **C** : ≥50 (Acceptable)
- **D** : <50 (À améliorer)

```python
# app/algorithms/carrier_scoring.py
def score_carrier(stats: dict) -> dict:
    """
    Calcule le score de fiabilité d'un transporteur.
    
    Args:
        stats: {
            "total_bookings": int,
            "completed_bookings": int,
            "no_shows": int,
            "late_arrivals": int,
            "avg_delay_minutes": float,
            "anomaly_count": int,
            ...
        }
    
    Returns:
        {
            "score": float,          # 0-100
            "tier": str,             # A, B, C, D
            "components": dict,      # Détails des composants
            "reasons": list[str],    # Explications
            "confidence": float      # 0-1 (basé sur sample size)
        }
    """
    # Implémentation déterministe (pas de random)
    ...
```

#### Slot Recommender

**Critères de ranking** :

```
Rank Score = 
    Availability (40%) +        # Plus de capacité restante = meilleur
    Time Distance (30%) +       # Plus proche du requested_time = meilleur
    Carrier Buffer (20%) +      # Carrier faible score → préférer slots plus tôt
    Gate Preference (10%)       # Match gate préféré = bonus
```

**Stratégies** :
- `standard` : Ranking normal
- `buffer_recommended` : Carrier score <60 → préfère slots **plus tôt** (buffer)
- `no_candidates` : Aucun slot dispo
- `no_capacity` : Tous pleins

---

### 5. **Tools & Clients** (`app/tools/`)

Clients HTTP pour communiquer avec les backend services.

#### Structure

```
app/tools/
├── __init__.py
├── nest_client.py              # NestJS (:3001)
├── booking_service_client.py   # Booking (:3002)
├── slot_service_client.py      # Slot (:3003)
├── carrier_service_client.py   # Carrier (:3004)
├── analytics_data_client.py    # Analytics (:3005)
├── blockchain_service_client.py# Blockchain (:3010)
├── time_tool.py                # Utilitaires de temps
└── blockchain_tool.py          # Utilitaires blockchain
```

#### Connection Pooling

**Pattern singleton** pour réutiliser les connexions :

```python
# app/tools/carrier_service_client.py
_client: Optional[httpx.AsyncClient] = None

def get_client() -> httpx.AsyncClient:
    """Retourne le client singleton (connection pooling)."""
    global _client
    if _client is None:
        from app.core.config import settings
        _client = httpx.AsyncClient(
            timeout=settings.CARRIER_CLIENT_TIMEOUT,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20)
        )
    return _client

async def get_carrier_stats(
    carrier_id: str,
    auth_header: Optional[str] = None,
    request_id: Optional[str] = None
) -> dict:
    """GET /carriers/{id}/stats"""
    client = get_client()
    headers = {}
    if auth_header:
        headers["Authorization"] = auth_header
    if request_id:
        headers["x-request-id"] = request_id
    
    response = await client.get(
        f"{settings.CARRIER_SERVICE_URL}/api/carriers/{carrier_id}/stats",
        headers=headers
    )
    response.raise_for_status()
    return response.json()
```

#### Graceful Shutdown

```python
# app/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    yield
    # Shutdown
    from app.tools import aclose_all_clients
    await aclose_all_clients()
```

---

### 6. **Core** (`app/core/`)

Utilitaires centraux (config, logging, erreurs, sécurité).

#### Structure

```
app/core/
├── __init__.py
├── config.py       # Settings (env vars)
├── logging.py      # setup_logging(), TraceIdFilter
├── errors.py       # AppError, ValidationError, etc.
└── security.py     # require_auth(), require_role()
```

#### Configuration

```python
# app/core/config.py
class Settings:
    # Application
    APP_ENV: str = os.getenv("APP_ENV", "dev")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Services
    NEST_BASE_URL: str = os.getenv("NEST_BASE_URL", "http://localhost:3001")
    BOOKING_SERVICE_URL: str = os.getenv("BOOKING_SERVICE_URL", "http://localhost:3002")
    CARRIER_SERVICE_URL: str = os.getenv("CARRIER_SERVICE_URL", "http://localhost:3004")
    # ...
    
    # Timeouts
    DEFAULT_CLIENT_TIMEOUT: float = float(os.getenv("DEFAULT_CLIENT_TIMEOUT", "10.0"))

settings = Settings()
```

#### Logging avec Trace ID

```python
# app/core/logging.py
from contextvars import ContextVar

TRACE_ID: ContextVar[str] = ContextVar("trace_id", default="")

def set_trace_id(trace_id: str):
    TRACE_ID.set(trace_id)

def get_trace_id() -> str:
    return TRACE_ID.get()

class TraceIdFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = get_trace_id()
        return True

def setup_logging():
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format="%(asctime)s [%(trace_id)s] %(levelname)s %(name)s: %(message)s"
    )
    logger = logging.getLogger()
    logger.addFilter(TraceIdFilter())
```

---

## 📡 Endpoints API

### Authentication & RBAC

Tous les endpoints (sauf `/health`) nécessitent :

**Headers** :
```
Authorization: Bearer <token>
x-user-role: ADMIN | OPERATOR | CARRIER | ANON
x-user-id: <user_id>
x-carrier-id: <carrier_id>  # Pour CARRIER role uniquement
x-request-id: <trace_id>     # Optionnel (généré auto sinon)
```

**Règles RBAC** :

| Endpoint | ADMIN | OPERATOR | CARRIER | ANON |
|----------|-------|----------|---------|------|
| `/health` | ✅ | ✅ | ✅ | ✅ |
| `/ai/chat` | ✅ | ✅ | ✅ | ❌ |
| `/carriers/{id}/score` | ✅ (any) | ✅ (any) | ✅ (own only) | ❌ |
| `/slots/availability` | ✅ | ✅ | ✅ | ✅ (limited data) |
| `/slots/recommend` | ✅ | ✅ | ✅ | ❌ |
| `/traffic/forecast` | ✅ | ✅ | ❌ | ❌ |
| `/anomalies/recent` | ✅ | ✅ | ❌ | ❌ |
| `/analytics/stress` | ✅ | ✅ | ❌ | ❌ |

---

### Endpoints Détaillés

#### 🤖 Chatbot

```http
POST /api/ai/chat
Content-Type: application/json
Authorization: Bearer <token>
x-user-role: OPERATOR

{
  "message": "Score du transporteur 123 ?",
  "user_id": 1,
  "user_role": "OPERATOR",
  "conversation_id": "conv-abc123"  // Optionnel
}
```

**Response** :
```json
{
  "conversation_id": "conv-abc123",
  "message": "Le transporteur 123 a un score de 85.5/100 (Tier A)",
  "intent": "carrier_score",
  "entities": { "carrier_id": "123" },
  "agent": "carrier_score_agent",
  "data": {
    "carrier_id": "123",
    "score": 85.5,
    "tier": "A",
    "components": { "completion": 95.0, "on_time": 88.0, ... },
    "reasons": ["Excellent overall performance", ...]
  },
  "proofs": {
    "trace_id": "trace-xyz",
    "timestamp": "2026-02-05T00:30:00Z",
    "data_quality": "real"
  }
}
```

---

#### 📊 Carrier Score

```http
GET /api/carriers/123/score?window_days=90
Authorization: Bearer <token>
x-user-role: OPERATOR
```

**Response** :
```json
{
  "message": "Carrier 123 score: 85.5/100 (Tier A)",
  "data": {
    "carrier_id": "123",
    "score": 85.5,
    "tier": "A",
    "components": {
      "completion": 95.0,
      "on_time": 88.0,
      "no_show": 90.0,
      "anomaly": 85.0,
      "dwell_efficiency": 75.0
    },
    "reasons": [
      "Excellent overall performance",
      "High completion rate (98.5%)",
      "Excellent punctuality record"
    ],
    "confidence": 1.0,
    "stats_summary": {
      "total_bookings": 150,
      "completion_rate": 98.5,
      "on_time_rate": 95.2,
      "no_show_rate": 0.7
    }
  },
  "proofs": {
    "trace_id": "trace-xyz",
    "timestamp": "2026-02-05T00:30:00Z",
    "model": "carrier_scoring_v1",
    "data_quality": "real"
  }
}
```

---

#### 🕐 Slot Recommendation

```http
POST /api/slots/recommend
Content-Type: application/json
Authorization: Bearer <token>
x-user-role: CARRIER
x-carrier-id: 456

{
  "terminal": "A",
  "date": "2026-02-06",
  "requested_time": "09:00",
  "gate": "G1"  // Optionnel
}
```

**Response** :
```json
{
  "message": "Generated 5 slot recommendations",
  "data": {
    "recommended": [
      {
        "start": "2026-02-06T08:30:00Z",
        "terminal": "A",
        "gate": "G2",
        "remaining": 5,
        "capacity": 10,
        "rank_score": 95.0,
        "rank_reasons": [
          "High availability (5/10 spots)",
          "Earlier by 30min - good buffer"
        ]
      },
      {
        "start": "2026-02-06T09:00:00Z",
        "terminal": "A",
        "gate": "G1",
        "remaining": 3,
        "capacity": 10,
        "rank_score": 92.0,
        "rank_reasons": [
          "Exact time match",
          "Matches requested gate G1"
        ]
      }
    ],
    "ranked": [...],  // Tous les slots scorés
    "strategy": "buffer_recommended",  // ou "standard"
    "reasons": [
      "Carrier score is 55/100 - recommending earlier slots for reliability buffer",
      "Top recommendation: 2026-02-06T08:30 at A/G2 (5/10 available)"
    ]
  },
  "proofs": {
    "trace_id": "trace-xyz",
    "carrier_score_used": 55.0,
    "algorithm": "slot_recommender_v1"
  }
}
```

---

#### 🚨 Recent Anomalies

```http
GET /api/anomalies/recent?terminal=A&days=7&limit=50
Authorization: Bearer <token>
x-user-role: OPERATOR
```

**Response** :
```json
{
  "message": "Found 3 recent anomalies",
  "data": {
    "anomalies": [
      {
        "type": "no_show",
        "timestamp": "2026-02-04T14:30:00Z",
        "terminal": "A",
        "gate": "G1",
        "carrier_id": "789",
        "booking_ref": "BK-456",
        "severity": "high",
        "description": "No-show without cancellation"
      }
    ],
    "terminal": "A",
    "days": 7,
    "count": 3
  },
  "proofs": {
    "trace_id": "trace-xyz"
  }
}
```

---

#### 🚦 Traffic Forecast

```http
GET /api/traffic/forecast?terminal=A&horizon_hours=24
Authorization: Bearer <token>
x-user-role: OPERATOR
```

**Response** :
```json
{
  "message": "Traffic forecast generated",
  "data": {
    "terminal": "A",
    "forecast": [
      {
        "hour": "2026-02-05T09:00:00Z",
        "predicted_load": 85,
        "confidence": 0.9
      },
      {
        "hour": "2026-02-05T10:00:00Z",
        "predicted_load": 92,
        "confidence": 0.85
      }
    ],
    "peak_hour": "2026-02-05T10:00:00Z",
    "peak_load": 92
  },
  "proofs": {
    "trace_id": "trace-xyz",
    "model": "traffic_forecast_v1"
  }
}
```

---

## 🛠️ Guide d'Extension

### Ajouter un Nouvel Agent

**Exemple** : Créer un `ParkingAgent` pour recommander des parkings.

#### 1. Créer le fichier agent

```python
# app/agents/parking_agent.py
from app.agents.base_agent import BaseAgent
import logging

logger = logging.getLogger(__name__)

class ParkingAgent(BaseAgent):
    """Agent pour recommandation de parking."""
    
    async def execute(self, context: dict) -> dict:
        # 1. Extraire les entités
        terminal = context["entities"].get("terminal")
        vehicle_type = context["entities"].get("vehicle_type", "truck")
        
        # 2. Appeler le service backend
        from app.tools.parking_service_client import get_available_parking
        
        parking_data = await get_available_parking(
            terminal=terminal,
            vehicle_type=vehicle_type,
            auth_header=context.get("auth_header")
        )
        
        # 3. Traiter les données (optionnel : algorithme de ranking)
        # ...
        
        # 4. Formater la réponse
        return {
            "message": f"Found {len(parking_data)} parking spots at terminal {terminal}",
            "data": {
                "terminal": terminal,
                "vehicle_type": vehicle_type,
                "parking_spots": parking_data
            },
            "proofs": {
                "trace_id": context["trace_id"],
                "timestamp": datetime.utcnow().isoformat()
            }
        }
```

#### 2. Enregistrer l'agent

```python
# app/agents/registry.py
from app.agents.parking_agent import ParkingAgent

AGENT_CLASSES = {
    # ... existing ...
    "parking_recommendation": ParkingAgent,
}
```

#### 3. Ajouter l'intent

```python
# app/constants/intents.py
PARKING_RECOMMENDATION = "parking_recommendation"

ALL_INTENTS = [
    # ... existing ...
    PARKING_RECOMMENDATION,
]

INTENT_TO_AGENT = {
    # ... existing ...
    PARKING_RECOMMENDATION: "parking_agent",
}
```

#### 4. Ajouter les patterns de détection

```python
# app/orchestrator/intent_detector.py
INTENT_PATTERNS = {
    # ... existing ...
    "parking_recommendation": [
        r"(?:parking|stationnement).*(?:disponible|libre).*terminal\s*(?P<terminal>[A-Z])",
        r"où\s+(?:garer|stationner).*terminal\s*(?P<terminal>[A-Z])",
    ]
}
```

#### 5. Créer le client HTTP (si nécessaire)

```python
# app/tools/parking_service_client.py
import httpx
from typing import Optional

_client: Optional[httpx.AsyncClient] = None

def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        from app.core.config import settings
        _client = httpx.AsyncClient(
            timeout=10.0,
            limits=httpx.Limits(max_connections=50)
        )
    return _client

async def get_available_parking(
    terminal: str,
    vehicle_type: str,
    auth_header: Optional[str] = None
) -> dict:
    client = get_client()
    headers = {}
    if auth_header:
        headers["Authorization"] = auth_header
    
    response = await client.get(
        f"http://localhost:3006/api/parking/availability",
        params={"terminal": terminal, "vehicle_type": vehicle_type},
        headers=headers
    )
    response.raise_for_status()
    return response.json()
```

#### 6. Ajouter un endpoint REST direct (optionnel)

```python
# app/api/parking.py
from fastapi import APIRouter, Request
import uuid

router = APIRouter(prefix="/parking", tags=["parking"])

@router.get("/availability")
async def get_parking_availability(
    terminal: str,
    vehicle_type: str = "truck",
    request: Request = None
):
    from app.models.loader import get_model
    
    model = get_model("parking_recommendation")
    result = await model.predict(
        input={"terminal": terminal, "vehicle_type": vehicle_type},
        context={
            "auth_header": request.headers.get("authorization"),
            "trace_id": request.headers.get("x-request-id", str(uuid.uuid4()))
        }
    )
    
    return {
        "message": result["message"],
        "data": result["data"],
        "proofs": result["proofs"]
    }
```

#### 7. Enregistrer le router

```python
# app/api/router.py
ROUTER_CONFIGS = [
    # ... existing ...
    ("parking", "/parking", ["Parking"], "parking_router"),
]
```

✅ **Voilà ! Votre nouveau `ParkingAgent` est intégré.**

---

### Ajouter un Nouvel Algorithme

**Exemple** : Créer `gate_optimizer.py` pour optimiser l'affectation des portes.

#### 1. Créer le fichier algorithme

```python
# app/algorithms/gate_optimizer.py
from typing import List, Dict, Any

def optimize_gate_assignment(
    bookings: List[Dict[str, Any]],
    available_gates: List[str],
    constraints: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Optimise l'affectation des portes basée sur les contraintes.
    
    Args:
        bookings: Liste des réservations
        available_gates: Portes disponibles
        constraints: Contraintes (capacité, exclusions, etc.)
    
    Returns:
        {
            "assignments": [{"booking_id": "...", "gate": "G1"}, ...],
            "score": float,
            "reasoning": [str]
        }
    """
    # Algorithme déterministe
    # Par exemple : greedy assignment basé sur la proximité temporelle
    
    assignments = []
    for booking in bookings:
        # Logique d'affectation
        best_gate = _find_best_gate(booking, available_gates, constraints)
        assignments.append({
            "booking_id": booking["id"],
            "gate": best_gate,
            "score": _compute_assignment_score(booking, best_gate)
        })
    
    total_score = sum(a["score"] for a in assignments) / len(assignments)
    
    return {
        "assignments": assignments,
        "score": total_score,
        "reasoning": [
            f"Assigned {len(assignments)} bookings to {len(set(a['gate'] for a in assignments))} gates",
            f"Average assignment score: {total_score:.2f}"
        ]
    }

def _find_best_gate(booking, gates, constraints):
    # Implémentation simplifiée
    return gates[0]

def _compute_assignment_score(booking, gate):
    # Scoring basé sur critères
    return 85.0
```

#### 2. Exporter l'algorithme

```python
# app/algorithms/__init__.py
from app.algorithms.gate_optimizer import optimize_gate_assignment

__all__ = [
    # ... existing ...
    "optimize_gate_assignment",
]
```

#### 3. Utiliser dans un agent

```python
# app/agents/gate_optimizer_agent.py
from app.algorithms.gate_optimizer import optimize_gate_assignment

class GateOptimizerAgent(BaseAgent):
    async def execute(self, context: dict) -> dict:
        # Fetcher les données
        bookings = await get_bookings(...)
        gates = await get_available_gates(...)
        
        # Appeler l'algorithme
        result = optimize_gate_assignment(bookings, gates, {})
        
        return {
            "message": f"Optimized gate assignments with score {result['score']:.1f}",
            "data": result,
            "proofs": {"trace_id": context["trace_id"]}
        }
```

---

## ⚙️ Configuration & Déploiement

### Variables d'Environnement

Créer `.env` à la racine du service :

```bash
# Application
APP_ENV=production
LOG_LEVEL=INFO
MODEL_MODE_DEFAULT=real

# Service URLs
NEST_BASE_URL=http://nest-backend:3001
BOOKING_SERVICE_URL=http://booking-service:3002
SLOT_SERVICE_URL=http://slot-service:3003
CARRIER_SERVICE_URL=http://carrier-service:3004
ANALYTICS_DATA_URL=http://analytics-service:3005
BLOCKCHAIN_AUDIT_SERVICE_URL=http://blockchain-service:3010

# Timeouts (secondes)
DEFAULT_CLIENT_TIMEOUT=10.0
NEST_CLIENT_TIMEOUT=5.0
CARRIER_CLIENT_TIMEOUT=8.0

# CORS
CORS_ORIGINS=http://localhost:3000,https://smartport.example.com

# Security (optionnel)
JWT_SECRET_KEY=your-secret-key-here
```

---

### Installation & Démarrage

#### Local (Développement)

```bash
# 1. Installer les dépendances
cd src/modules/ai_service
pip install -r requirements.txt

# 2. Copier .env.example → .env et configurer
cp .env.example .env
nano .env

# 3. Démarrer le serveur
python -m uvicorn app.main:app --reload --port 8000

# Ou avec hot-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Accès** : http://localhost:8000/docs (Swagger UI)

---

#### Docker

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# Build
docker build -t smartport-ai-service .

# Run
docker run -p 8000:8000 \
  -e NEST_BASE_URL=http://host.docker.internal:3001 \
  -e LOG_LEVEL=INFO \
  smartport-ai-service
```

---

#### Docker Compose (avec tous les services)

```yaml
# docker-compose.yml
version: '3.8'

services:
  ai_service:
    build: ./src/modules/ai_service
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=production
      - NEST_BASE_URL=http://nest-backend:3001
      - BOOKING_SERVICE_URL=http://booking-service:3002
      - CARRIER_SERVICE_URL=http://carrier-service:3004
    depends_on:
      - nest-backend
      - booking-service
      - carrier-service
    networks:
      - smartport-network

  nest-backend:
    # ... config NestJS ...
    ports:
      - "3001:3001"
    networks:
      - smartport-network

  booking-service:
    # ... config booking service ...
    ports:
      - "3002:3002"
    networks:
      - smartport-network

networks:
  smartport-network:
    driver: bridge
```

```bash
docker-compose up -d
```

---

## 🧪 Tests & Validation

### Structure des Tests

```
app/tests/
├── __init__.py
├── conftest.py              # Fixtures pytest
├── test_algorithms.py       # Tests des algorithmes
├── test_agents.py           # Tests des agents
└── test_api.py              # Tests des endpoints
```

---

### Exécuter les Tests

```bash
# Tous les tests
python -m pytest app/tests/ -v

# Tests spécifiques
python -m pytest app/tests/test_algorithms.py -v
python -m pytest app/tests/test_agents.py::test_carrier_score_agent_success -v

# Avec coverage
python -m pytest app/tests/ --cov=app --cov-report=html
```

---

### Exemple de Test

```python
# app/tests/test_algorithms.py
import pytest
from app.algorithms.carrier_scoring import score_carrier

def test_carrier_scoring_high_performance():
    """Test scoring d'un transporteur performant."""
    stats = {
        "total_bookings": 100,
        "completed_bookings": 98,
        "cancelled_bookings": 2,
        "no_shows": 0,
        "late_arrivals": 3,
        "avg_delay_minutes": 2.5,
        "avg_dwell_minutes": 40.0,
        "anomaly_count": 1
    }
    
    result = score_carrier(stats)
    
    assert result["score"] >= 85.0, "Score devrait être ≥85 pour Tier A"
    assert result["tier"] == "A"
    assert result["confidence"] >= 0.5
    assert "Excellent" in result["reasons"][0]


def test_carrier_scoring_zero_bookings():
    """Test edge case: aucune réservation."""
    stats = {
        "total_bookings": 0,
        "completed_bookings": 0,
        "no_shows": 0,
        "late_arrivals": 0,
        "avg_delay_minutes": 0.0,
        "avg_dwell_minutes": 0.0,
        "anomaly_count": 0
    }
    
    result = score_carrier(stats)
    
    assert result["score"] == 0.0
    assert result["tier"] == "D"
    assert result["confidence"] == 0.0
    assert "No booking history" in result["reasons"][0]
```

---

## 📚 Ressources Supplémentaires

### Documentation Technique

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [httpx Async Client](https://www.python-httpx.org/async/)
- [Pydantic V2](https://docs.pydantic.dev/)

### Fichiers Importants

- [`README.md`](./README.md) - Overview du projet
- [`requirements.txt`](./requirements.txt) - Dépendances Python
- [`.env.example`](./.env.example) - Template de configuration
- [`app/main.py`](./app/main.py) - Point d'entrée FastAPI

---

## 🎯 Checklist d'Implémentation

### Phase 1 : Setup Initial
- [ ] Cloner le repo et installer les dépendances
- [ ] Configurer `.env` avec les URLs des services backend
- [ ] Démarrer le serveur : `uvicorn app.main:app --reload`
- [ ] Tester `/health` : http://localhost:8000/health
- [ ] Accéder à Swagger UI : http://localhost:8000/docs

### Phase 2 : Intégration Backend
- [ ] Vérifier connectivité NestJS (:3001)
- [ ] Tester endpoint carrier scoring avec vrai backend
- [ ] Tester slot availability
- [ ] Configurer les timeouts appropriés

### Phase 3 : Tests Fonctionnels
- [ ] Exécuter `pytest app/tests/` → tous les tests passent
- [ ] Tester chatbot avec message réel
- [ ] Tester endpoints REST directs (Postman/curl)
- [ ] Vérifier les logs (trace_id propagation)

### Phase 4 : Déploiement
- [ ] Build Docker image
- [ ] Déployer sur environnement staging
- [ ] Tester avec dashboard réel
- [ ] Monitorer les performances (response times)

### Phase 5 : Extension (si applicable)
- [ ] Ajouter nouveaux agents selon besoins
- [ ] Implémenter nouveaux algorithmes
- [ ] Connecter nouveaux services backend
- [ ] Mettre à jour la documentation

---

## 🆘 Support & Contact

Pour toute question sur l'architecture ou l'implémentation :

1. **Lire la documentation** : `ARCHITECTURE.md` (ce fichier), `README.md`
2. **Consulter les exemples** : `app/agents/`, `app/algorithms/`
3. **Tester localement** : `python -m pytest app/tests/ -v`
4. **Vérifier les logs** : Rechercher `[trace_id]` pour suivre une requête

---

**Version** : 1.0  
**Dernière mise à jour** : 2026-02-05  
**Auteur** : Équipe Smart Port AI
