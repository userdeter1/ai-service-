"""
API Package - FastAPI Routers

Exports all API routers for main app registration.
"""

from fastapi import APIRouter

# Import routers from modules
try:
    from app.api.admin import router as admin_router
except ImportError:
    admin_router = None

try:
    from app.api.operator import router as operator_router
except ImportError:
    operator_router = None

try:
    from app.api.carriers import router as carriers_router
except ImportError:
    carriers_router = None

try:
    from app.api.slots import router as slots_router
except ImportError:
    slots_router = None

try:
    from app.api.traffic import router as traffic_router
except ImportError:
    traffic_router = None

try:
    from app.api.anomalies import router as anomalies_router
except ImportError:
    anomalies_router = None

try:
    from app.api.chat import router as chat_router
except ImportError:
    chat_router = None

# API Version
API_VERSION = "1.0.0"

__all__ = [
    "admin_router",
    "operator_router",
    "carriers_router",
    "slots_router",
    "traffic_router",
    "anomalies_router",
    "chat_router",
    "API_VERSION",
]
