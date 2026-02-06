"""
Tools Package

Provides service clients, utilities, and tool functions for agents and models.

Service Clients (with connection pooling and graceful shutdown):
- nest_client: NestJS backend client
- booking_service_client: Booking service HTTP client
- carrier_service_client: Carrier service HTTP client
- slot_service_client: Slot service HTTP client
- blockchain_service_client: Blockchain audit service HTTP client
- analytics_data_client: Analytics data aggregator

Utility Tools:
- time_tool: Date/time parsing and utilities
- blockchain_tool: High-level blockchain verification wrapper

NOTE: Clients are NOT imported eagerly to avoid connection side effects at module import.
Import specific clients as needed: `from app.tools import nest_client`
"""

# DO NOT import clients eagerly here - they create httpx connections
# Agents should import specific clients as needed

# Export utility tools (no connection side effects)
from app.tools import time_tool
from app.tools import blockchain_tool

# Convenience re-exports for shutdown functions
# These can be imported without creating connections
__all__ = [
    # Utility modules
    "time_tool",
    "blockchain_tool",
    
    # Service client modules (import as needed - not eagerly loaded)
    # "nest_client",
    # "booking_service_client",
    # "carrier_service_client",
    # "slot_service_client",
    # "blockchain_service_client",
    # "analytics_data_client",
]

# Shutdown helper (aggregates all client closures)
async def aclose_all_clients() -> None:
    """
    Close all HTTP clients gracefully.
    Should be called during FastAPI shutdown (lifespan).
    
    This is a convenience function that closes all clients.
    Individual clients can also be closed via their own aclose_client() functions.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    clients_to_close = [
        ("nest_client", "app.tools.nest_client"),
        ("booking_service_client", "app.tools.booking_service_client"),
        ("carrier_service_client", "app.tools.carrier_service_client"),
        ("slot_service_client", "app.tools.slot_service_client"),
        ("blockchain_service_client", "app.tools.blockchain_service_client"),
        ("analytics_data_client", "app.tools.analytics_data_client"),
    ]
    
    for client_name, module_path in clients_to_close:
        try:
            module = __import__(module_path, fromlist=["aclose_client"])
            if hasattr(module, "aclose_client"):
                await module.aclose_client()
                logger.info(f"Closed {client_name}")
        except Exception as e:
            logger.error(f"Error closing {client_name}: {e}")
