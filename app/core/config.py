"""
Core Configuration Module

Centralizes environment configuration for the FastAPI AI service.
Provides a singleton Settings object with defaults aligned to existing service clients.

Usage:
    from app.core.config import settings
    
    print(settings.APP_ENV)
    print(settings.NEST_BASE_URL)
"""

import os
from typing import List, Optional


class Settings:
    """
    Application settings loaded from environment variables.
    
    Provides centralized configuration with sensible defaults that align
    with existing service client environment variable names.
    """
    
    # ==================== Application Settings ====================
    
    @property
    def APP_ENV(self) -> str:
        """Application environment: dev, staging, production"""
        return os.getenv("APP_ENV", "dev")
    
    @property
    def LOG_LEVEL(self) -> str:
        """Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL"""
        return os.getenv("LOG_LEVEL", "INFO")
    
    @property
    def MODEL_MODE_DEFAULT(self) -> str:
        """Default model mode: real or mvp"""
        return os.getenv("MODEL_MODE_DEFAULT", "real")
    
    # ==================== Service URLs ====================
    
    @property
    def NEST_BASE_URL(self) -> str:
        """NestJS backend service URL (aligns with nest_client.py)"""
        return os.getenv("NEST_BASE_URL", "http://localhost:3001")
    
    @property
    def BOOKING_SERVICE_URL(self) -> str:
        """Booking service URL (aligns with booking_service_client.py)"""
        return os.getenv("BOOKING_SERVICE_URL", "http://localhost:3002")
    
    @property
    def CARRIER_SERVICE_URL(self) -> str:
        """Carrier service URL (aligns with carrier_service_client.py)"""
        return os.getenv("CARRIER_SERVICE_URL", "http://localhost:3004")
    
    @property
    def SLOT_SERVICE_URL(self) -> str:
        """Slot service URL (aligns with slot_service_client.py)"""
        return os.getenv("SLOT_SERVICE_URL", "http://localhost:3003")
    
    @property
    def BLOCKCHAIN_AUDIT_SERVICE_URL(self) -> Optional[str]:
        """Blockchain audit service URL (optional, aligns with blockchain_service_client.py)"""
        return os.getenv("BLOCKCHAIN_AUDIT_SERVICE_URL", "http://localhost:3010")
    
    @property
    def ANALYTICS_DATA_SERVICE_URL(self) -> Optional[str]:
        """Analytics data service URL (optional, aligns with analytics_data_client.py)"""
        return os.getenv("ANALYTICS_DATA_SERVICE_URL", "http://localhost:3005")
    
    # ==================== HTTP Client Settings ====================
    
    @property
    def DEFAULT_CLIENT_TIMEOUT(self) -> float:
        """Default HTTP client timeout in seconds"""
        return float(os.getenv("DEFAULT_CLIENT_TIMEOUT", "10.0"))
    
    @property
    def DEFAULT_CLIENT_MAX_CONNECTIONS(self) -> int:
        """Default maximum HTTP connections in pool"""
        return int(os.getenv("DEFAULT_CLIENT_MAX_CONNECTIONS", "50"))
    
    @property
    def DEFAULT_CLIENT_MAX_KEEPALIVE(self) -> int:
        """Default maximum keepalive connections in pool"""
        return int(os.getenv("DEFAULT_CLIENT_MAX_KEEPALIVE", "10"))
    
    # Specific client timeouts (if set, override default)
    
    @property
    def NEST_CLIENT_TIMEOUT(self) -> float:
        """NestJS client timeout"""
        return float(os.getenv("NEST_CLIENT_TIMEOUT", str(self.DEFAULT_CLIENT_TIMEOUT)))
    
    @property
    def BOOKING_CLIENT_TIMEOUT(self) -> float:
        """Booking service client timeout"""
        return float(os.getenv("BOOKING_CLIENT_TIMEOUT", str(self.DEFAULT_CLIENT_TIMEOUT)))
    
    @property
    def CARRIER_CLIENT_TIMEOUT(self) -> float:
        """Carrier service client timeout"""
        return float(os.getenv("CARRIER_CLIENT_TIMEOUT", str(self.DEFAULT_CLIENT_TIMEOUT)))
    
    @property
    def SLOT_CLIENT_TIMEOUT(self) -> float:
        """Slot service client timeout"""
        return float(os.getenv("SLOT_CLIENT_TIMEOUT", str(self.DEFAULT_CLIENT_TIMEOUT)))
    
    @property
    def BLOCKCHAIN_CLIENT_TIMEOUT(self) -> float:
        """Blockchain service client timeout"""
        return float(os.getenv("BLOCKCHAIN_CLIENT_TIMEOUT", str(self.DEFAULT_CLIENT_TIMEOUT)))
    
    @property
    def ANALYTICS_CLIENT_TIMEOUT(self) -> float:
        """Analytics service client timeout"""
        return float(os.getenv("ANALYTICS_CLIENT_TIMEOUT", str(self.DEFAULT_CLIENT_TIMEOUT)))
    
    # ==================== CORS Settings ====================
    
    @property
    def CORS_ORIGINS(self) -> List[str]:
        """Allowed CORS origins"""
        origins_str = os.getenv("CORS_ORIGINS", "*")
        if origins_str == "*":
            return ["*"]
        return [origin.strip() for origin in origins_str.split(",")]
    
    @property
    def CORS_ALLOW_CREDENTIALS(self) -> bool:
        """Allow credentials in CORS requests"""
        return os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
    
    # ==================== Security Settings ====================
    
    @property
    def INTERNAL_API_KEY(self) -> Optional[str]:
        """Internal API key for service-to-service authentication (optional)"""
        return os.getenv("INTERNAL_API_KEY")
    
    @property
    def JWT_SECRET(self) -> Optional[str]:
        """JWT secret for token validation (optional)"""
        return os.getenv("JWT_SECRET")
    
    @property
    def JWT_ALGORITHM(self) -> str:
        """JWT algorithm for token validation"""
        return os.getenv("JWT_ALGORITHM", "HS256")
    
    # ==================== Database Settings ====================
    
    @property
    def CHAT_DB_PATH(self) -> str:
        """SQLite database path for chat persistence"""
        return os.getenv("CHAT_DB_PATH", "./data/chat.db")
    
    # ==================== Feature Flags ====================
    
    @property
    def ENABLE_BLOCKCHAIN_AUDIT(self) -> bool:
        """Enable blockchain audit features"""
        return os.getenv("ENABLE_BLOCKCHAIN_AUDIT", "false").lower() == "true"
    
    @property
    def ENABLE_ANALYTICS(self) -> bool:
        """Enable analytics features"""
        return os.getenv("ENABLE_ANALYTICS", "true").lower() == "true"
    
    @property
    def ENABLE_CHAT_PERSISTENCE(self) -> bool:
        """Enable chat persistence to database"""
        return os.getenv("ENABLE_CHAT_PERSISTENCE", "true").lower() == "true"


# ==================== Singleton Instance ====================

_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get the singleton Settings instance.
    
    Returns:
        Settings object with configuration values
        
    Example:
        >>> from app.core.config import get_settings
        >>> settings = get_settings()
        >>> print(settings.APP_ENV)
        'dev'
    """
    global _settings
    
    if _settings is None:
        _settings = Settings()
    
    return _settings


# Convenience singleton for direct import
settings = get_settings()


# ==================== Helper Functions ====================

def is_production() -> bool:
    """
    Check if the application is running in production environment.
    
    Returns:
        True if APP_ENV is 'production' or 'prod'
        
    Example:
        >>> from app.core.config import is_production
        >>> if is_production():
        ...     print("Running in production mode")
    """
    env = settings.APP_ENV.lower()
    return env in ("production", "prod")


def is_development() -> bool:
    """
    Check if the application is running in development environment.
    
    Returns:
        True if APP_ENV is 'dev' or 'development'
    """
    env = settings.APP_ENV.lower()
    return env in ("dev", "development")
