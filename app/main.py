"""
FastAPI Application Entry Point

Main application with proper lifecycle management for HTTP clients.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown for HTTP clients.
    """
    # Startup
    logger.info("AI Service starting up...")
    
    yield
    
    # Shutdown - close all HTTP clients gracefully
    logger.info("AI Service shutting down...")
    
    try:
        from app.tools import nest_client
        await nest_client.aclose_client()
        logger.info("Closed NestJS client")
    except Exception as e:
        logger.error(f"Error closing nest_client: {e}")
    
    try:
        from app.tools import booking_service_client
        await booking_service_client.aclose_client()
        logger.info("Closed Booking Service client")
    except Exception as e:
        logger.error(f"Error closing booking_service_client: {e}")
    
    try:
        from app.tools import carrier_service_client
        await carrier_service_client.aclose_client()
        logger.info("Closed Carrier Service client")
    except Exception as e:
        logger.error(f"Error closing carrier_service_client: {e}")
    
    try:
        from app.tools import slot_service_client
        await slot_service_client.aclose_client()
        logger.info("Closed Slot Service client")
    except Exception as e:
        logger.error(f"Error closing slot_service_client: {e}")
    
    try:
        from app.tools import blockchain_service_client
        await blockchain_service_client.aclose_client()
        logger.info("Closed Blockchain Service client")
    except Exception as e:
        logger.error(f"Error closing blockchain_service_client: {e}")
    
    try:
        from app.tools import analytics_data_client
        await analytics_data_client.aclose_client()
        logger.info("Closed Analytics Data client")
    except Exception as e:
        logger.error(f"Error closing analytics_data_client: {e}")
    
    logger.info("AI Service shutdown complete")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="AI Service - Truck Booking Management",
    description="Intelligent chatbot for smart port operations",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
try:
    from app.api.chat import router as chat_router
    app.include_router(chat_router, prefix="/api", tags=["chat"])
    logger.info("Registered chat router")
except ImportError as e:
    logger.warning(f"Could not import chat router: {e}")

try:
    from app.api.traffic import router as traffic_router
    app.include_router(traffic_router, prefix="/api", tags=["traffic"])
    logger.info("Registered traffic router")
except ImportError as e:
    logger.warning(f"Could not import traffic router: {e}")

try:
    from app.api.analytics import router as analytics_router
    app.include_router(analytics_router, prefix="/api", tags=["analytics"])
    logger.info("Registered analytics router")
except ImportError as e:
    logger.warning(f"Could not import analytics router: {e}")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "AI Service",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "service": "ai_service",
        "components": {
            "api": "ok",
            "orchestrator": "ok"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
