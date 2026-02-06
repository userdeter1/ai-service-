"""
Central API Router

Aggregates all endpoint routers for the Smart Port AI Service.
Handles missing routers gracefully to allow partial service operation.
"""

import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)

# Main API router
api_router = APIRouter()

# Router configurations: (module_name, prefix, tag, router_alias)
ROUTER_CONFIGS = [
    ("chat", "/ai", ["AI Chat"], "chat_router"),
    ("traffic", "/traffic", ["Traffic Forecast"], "traffic_router"),
    ("anomalies", "/anomalies", ["Anomaly Detection"], "anomalies_router"),
    ("slots", "/slots", ["Slot Recommendation"], "slots_router"),
    ("carriers", "/carriers", ["Carrier Scoring"], "carriers_router"),
    ("admin", "/admin", ["Admin Analytics"], "admin_router"),
    ("operator", "/operator", ["Operator Analytics"], "operator_router"),
]


def _include_router_safe(module_name: str, prefix: str, tags: list, alias: str) -> None:
    """
    Safely import and include a router module.
    Logs warnings/errors but does not raise exceptions.
    """
    try:
        # Dynamic import
        module = __import__(f"app.api.{module_name}", fromlist=["router"])
        router = getattr(module, "router")
        
        # Include in main router
        api_router.include_router(router, prefix=prefix, tags=tags)
        logger.info(f"✓ Registered {module_name} router at {prefix}")
        
    except ImportError:
        logger.warning(f"⚠ Router module 'app.api.{module_name}' not found - skipping")
    except AttributeError:
        logger.warning(f"⚠ Module 'app.api.{module_name}' has no 'router' attribute - skipping")
    except Exception as e:
        logger.error(f"✗ Failed to register {module_name} router: {e}")


# Register all routers
for module_name, prefix, tags, alias in ROUTER_CONFIGS:
    _include_router_safe(module_name, prefix, tags, alias)

logger.info(f"API router initialized with {len(api_router.routes)} routes")
