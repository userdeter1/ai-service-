"""
Core Package

Centralized configuration, logging, error handling, and security utilities
for the FastAPI AI service.

Modules:
- config: Environment configuration and settings
- logging: Structured logging with trace_id support
- errors: Standardized error classes and HTTP conversion
- security: Authentication and authorization helpers

Usage:
    from app.core import settings, setup_logging, set_trace_id
    from app.core import ValidationError, UnauthorizedError
    from app.core import require_auth, require_role
"""

# Configuration
from app.core.config import settings, get_settings, is_production, is_development

# Logging
from app.core.logging import (
    setup_logging,
    set_trace_id,
    get_trace_id,
    get_logger
)

# Errors
from app.core.errors import (
    AppError,
    ValidationError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    InternalError,
    error_payload,
    from_http_exception,
    to_http_exception
)

# Security
from app.core.security import (
    require_auth,
    require_role,
    has_role,
    is_admin,
    is_operator,
    is_carrier,
    parse_bearer_token
)

__all__ = [
    # Config
    "settings",
    "get_settings",
    "is_production",
    "is_development",
    
    # Logging
    "setup_logging",
    "set_trace_id",
    "get_trace_id",
    "get_logger",
    
    # Errors
    "AppError",
    "ValidationError",
    "UnauthorizedError",
    "ForbiddenError",
    "NotFoundError",
    "ServiceUnavailableError",
    "InternalError",
    "error_payload",
    "from_http_exception",
    "to_http_exception",
    
    # Security
    "require_auth",
    "require_role",
    "has_role",
    "is_admin",
    "is_operator",
    "is_carrier",
    "parse_bearer_token",
]
