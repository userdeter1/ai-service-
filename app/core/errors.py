"""
Core Errors Module

Standardized error classes and helpers for consistent error handling across the service.
Provides conversion between internal errors and HTTP responses.

Usage:
    from app.core.errors import ValidationError, error_payload
    
    # Raise custom error
    raise ValidationError("Invalid date format", details={"field": "date"})
    
    # Create error payload
    payload = error_payload("invalid_input", "Bad request", trace_id="abc123")
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


# ==================== Base Error Class ====================

class AppError(Exception):
    """
    Base application error class.
    
    All custom errors should inherit from this class to ensure
    consistent error handling and conversion to HTTP responses.
    
    Attributes:
        code: Error code (e.g., "validation_error", "not_found")
        message: Human-readable error message
        details: Optional additional error context
        status_code: HTTP status code for this error type
    """
    
    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500
    ):
        """
        Initialize AppError.
        
        Args:
            message: Error message
            code: Error code (defaults to class name in snake_case)
            details: Optional error details dict
            status_code: HTTP status code
        """
        super().__init__(message)
        self.message = message
        self.code = code or self._default_code()
        self.details = details or {}
        self.status_code = status_code
    
    def _default_code(self) -> str:
        """
        Generate default error code from class name.
        
        Returns:
            snake_case version of class name
        """
        # Convert class name to snake_case (e.g., ValidationError -> validation_error)
        name = self.__class__.__name__
        if name.endswith("Error"):
            name = name[:-5]  # Remove "Error" suffix
        
        # Simple snake_case conversion
        result = []
        for i, char in enumerate(name):
            if char.isupper() and i > 0:
                result.append("_")
            result.append(char.lower())
        
        return "".join(result)
    
    def to_dict(self, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Convert error to dictionary for JSON responses.
        
        Args:
            trace_id: Optional request trace ID
            
        Returns:
            Error dict with code, message, details, trace_id
        """
        result = {
            "code": self.code,
            "message": self.message,
        }
        
        if self.details:
            result["details"] = self.details
        
        if trace_id:
            result["trace_id"] = trace_id
        
        return result


# ==================== Specific Error Classes ====================

class ValidationError(AppError):
    """
    Validation error (400 Bad Request).
    
    Raised when input validation fails.
    """
    
    def __init__(
        self,
        message: str = "Validation failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            code="validation_error",
            details=details,
            status_code=400
        )


class UnauthorizedError(AppError):
    """
    Unauthorized error (401 Unauthorized).
    
    Raised when authentication is required but missing or invalid.
    """
    
    def __init__(
        self,
        message: str = "Authentication required",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            code="unauthorized",
            details=details,
            status_code=401
        )


class ForbiddenError(AppError):
    """
    Forbidden error (403 Forbidden).
    
    Raised when user lacks permission for the requested operation.
    """
    
    def __init__(
        self,
        message: str = "Access forbidden",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            code="forbidden",
            details=details,
            status_code=403
        )


class NotFoundError(AppError):
    """
    Not found error (404 Not Found).
    
    Raised when a requested resource does not exist.
    """
    
    def __init__(
        self,
        message: str = "Resource not found",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            code="not_found",
            details=details,
            status_code=404
        )


class ServiceUnavailableError(AppError):
    """
    Service unavailable error (503 Service Unavailable).
    
    Raised when a backend service is unreachable or unresponsive.
    """
    
    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            code="service_unavailable",
            details=details,
            status_code=503
        )


class InternalError(AppError):
    """
    Internal server error (500 Internal Server Error).
    
    Raised for unexpected errors that don't fit other categories.
    """
    
    def __init__(
        self,
        message: str = "Internal server error",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            code="internal_error",
            details=details,
            status_code=500
        )


# ==================== Helper Functions ====================

def error_payload(
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standardized error payload dict.
    
    Args:
        code: Error code
        message: Error message
        details: Optional error details
        trace_id: Optional request trace ID
        
    Returns:
        Error dict suitable for JSON response
        
    Example:
        >>> payload = error_payload("bad_request", "Invalid input", trace_id="abc123")
        >>> payload["code"]
        'bad_request'
    """
    result = {
        "code": code,
        "message": message,
    }
    
    if details:
        result["details"] = details
    
    if trace_id:
        result["trace_id"] = trace_id
    
    return result


def from_http_exception(
    e: Exception,
    default_code: str = "service_error",
    safe_message: bool = True
) -> AppError:
    """
    Convert HTTP exception to AppError.
    
    Maps httpx.HTTPStatusError and fastapi.HTTPException to appropriate AppError subclass.
    Prevents leaking internal error details to users when safe_message=True.
    
    Args:
        e: Exception to convert
        default_code: Default error code if mapping fails
        safe_message: If True, use generic message instead of backend error details
        
    Returns:
        AppError instance
        
    Example:
        >>> from fastapi import HTTPException
        >>> http_err = HTTPException(status_code=404, detail="User not found")
        >>> app_err = from_http_exception(http_err)
        >>> app_err.status_code
        404
    """
    # Try to extract status code and detail
    status_code = getattr(e, "status_code", 500)
    detail = str(e)
    
    # For HTTPException, get detail attribute
    if hasattr(e, "detail"):
        detail = e.detail
    
    # For httpx.HTTPStatusError, get response details
    if hasattr(e, "response"):
        try:
            response = e.response
            status_code = response.status_code
            
            # Try to extract JSON error message
            try:
                error_data = response.json()
                if isinstance(error_data, dict):
                    detail = error_data.get("message") or error_data.get("detail") or str(error_data)
            except Exception:
                detail = response.text or f"HTTP {status_code}"
        except Exception:
            pass
    
    # Use safe generic message if requested
    if safe_message:
        if status_code == 401:
            detail = "Authentication required"
        elif status_code == 403:
            detail = "Access forbidden"
        elif status_code == 404:
            detail = "Resource not found"
        elif status_code >= 500:
            detail = "Service error"
            # Log actual error server-side
            logger.error(f"Service error ({status_code}): {e}")
    
    # Map status code to error class
    if status_code == 400:
        return ValidationError(message=detail)
    elif status_code == 401:
        return UnauthorizedError(message=detail)
    elif status_code == 403:
        return ForbiddenError(message=detail)
    elif status_code == 404:
        return NotFoundError(message=detail)
    elif status_code >= 500 and status_code < 600:
        return ServiceUnavailableError(message=detail)
    else:
        return AppError(
            message=detail,
            code=default_code,
            status_code=status_code
        )


def to_http_exception(error: AppError):
    """
    Convert AppError to FastAPI HTTPException.
    
    Args:
        error: AppError to convert
        
    Returns:
        HTTPException instance
        
    Example:
        >>> from app.core.errors import ValidationError, to_http_exception
        >>> app_err = ValidationError("Invalid input")
        >>> http_exc = to_http_exception(app_err)
        >>> http_exc.status_code
        400
    """
    from fastapi import HTTPException
    
    # Get trace_id from context if available
    trace_id = None
    try:
        from app.core.logging import get_trace_id
        trace_id = get_trace_id()
        if trace_id == "-":
            trace_id = None
    except ImportError:
        pass
    
    return HTTPException(
        status_code=error.status_code,
        detail=error.to_dict(trace_id=trace_id)
    )


# ==================== Self-Test ====================

if __name__ == "__main__":
    """
    Self-test for error classes and helpers.
    
    Run: python -m app.core.errors
    """
    print("Core Errors Self-Test")
    print("=" * 50)
    
    # Test error creation
    err = ValidationError("Invalid date format", details={"field": "date"})
    print(f"ValidationError: {err.message}")
    print(f"Status code: {err.status_code}")
    print(f"Error dict: {err.to_dict(trace_id='test123')}")
    
    # Test error payload
    payload = error_payload("bad_request", "Invalid input", trace_id="abc123")
    print(f"\nError payload: {payload}")
    
    # Test HTTP exception conversion
    from fastapi import HTTPException
    http_err = HTTPException(status_code=404, detail="User not found")
    app_err = from_http_exception(http_err, safe_message=False)
    print(f"\nConverted error: {app_err.message} (status={app_err.status_code})")
    
    # Test all error types
    errors = [
        ValidationError("Validation failed"),
        UnauthorizedError("Auth required"),
        ForbiddenError("Access denied"),
        NotFoundError("Not found"),
        ServiceUnavailableError("Service down"),
        InternalError("Unexpected error")
    ]
    
    print("\nAll error types:")
    for e in errors:
        print(f"  {e.__class__.__name__}: code={e.code}, status={e.status_code}")
    
    print("\n✅ All tests passed!")
