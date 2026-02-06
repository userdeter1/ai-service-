"""
Core Logging Module

Provides centralized logging configuration with trace_id injection for request tracing.
Uses contextvars to propagate trace_id throughout async execution contexts.

Usage:
    # At application startup:
    from app.core.logging import setup_logging
    setup_logging()
    
    # In request handlers or agents:
    from app.core.logging import set_trace_id, get_trace_id
    import logging
    
    set_trace_id("abc123")
    logger = logging.getLogger(__name__)
    logger.info("Processing request")  # Will include trace_id in logs
"""

import logging
import sys
from contextvars import ContextVar
from typing import Optional


# ==================== Context Variables ====================

TRACE_ID: ContextVar[str] = ContextVar("trace_id", default="-")


def set_trace_id(trace_id: str) -> None:
    """
    Set the trace_id for the current async context.
    
    Args:
        trace_id: Unique identifier for the request/trace
        
    Example:
        >>> from app.core.logging import set_trace_id
        >>> set_trace_id("abc123")
    """
    TRACE_ID.set(trace_id)


def get_trace_id() -> str:
    """
    Get the trace_id for the current async context.
    
    Returns:
        Current trace_id or "-" if not set
        
    Example:
        >>> from app.core.logging import get_trace_id
        >>> trace_id = get_trace_id()
    """
    return TRACE_ID.get()


# ==================== Log Filters ====================

class TraceIdFilter(logging.Filter):
    """
    Logging filter that injects trace_id into log records.
    
    Reads trace_id from contextvar and adds it to the log record,
    making it available to formatters.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add trace_id to log record.
        
        Args:
            record: Log record to modify
            
        Returns:
            True (always allow log record through)
        """
        record.trace_id = get_trace_id()
        return True


# ==================== Logging Setup ====================

_logging_setup_done = False


def setup_logging(log_level: Optional[str] = None, force: bool = False) -> None:
    """
    Configure application-wide logging with trace_id support.
    
    Sets up:
    - Root logger level from settings or parameter
    - Console handler with structured formatting
    - TraceIdFilter for automatic trace_id injection
    
    This function is idempotent - calling it multiple times is safe
    unless force=True is specified.
    
    Args:
        log_level: Optional log level override (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        force: If True, reconfigure even if already set up
        
    Example:
        >>> from app.core.logging import setup_logging
        >>> setup_logging()
        >>> setup_logging("DEBUG")  # Override level
    """
    global _logging_setup_done
    
    # Skip if already configured (unless forced)
    if _logging_setup_done and not force:
        return
    
    # Determine log level
    if log_level is None:
        try:
            from app.core.config import settings
            log_level = settings.LOG_LEVEL
        except ImportError:
            log_level = "INFO"
    
    # Convert string to logging level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers if forcing reconfiguration
    if force:
        root_logger.handlers.clear()
    
    # Only add handler if none exist
    if not root_logger.handlers:
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        
        # Create formatter with trace_id
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(trace_id)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(formatter)
        
        # Add trace_id filter
        trace_filter = TraceIdFilter()
        console_handler.addFilter(trace_filter)
        
        # Add handler to root logger
        root_logger.addHandler(console_handler)
    
    # Mark as configured
    _logging_setup_done = True
    
    # Log initialization
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured with level: {log_level.upper()}")


def reset_logging() -> None:
    """
    Reset logging setup state.
    
    Useful for testing or when you need to reconfigure logging.
    Does not remove handlers - call setup_logging(force=True) after this.
    """
    global _logging_setup_done
    _logging_setup_done = False


# ==================== Convenience Functions ====================

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    This is a convenience wrapper around logging.getLogger()
    that ensures logging is set up.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Logger instance
        
    Example:
        >>> from app.core.logging import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Hello world")
    """
    # Ensure logging is set up
    if not _logging_setup_done:
        setup_logging()
    
    return logging.getLogger(name)


# ==================== Example Usage ====================

if __name__ == "__main__":
    """
    Example demonstrating trace_id logging.
    
    Run: python -m app.core.logging
    """
    # Setup logging
    setup_logging("DEBUG")
    
    logger = logging.getLogger(__name__)
    
    # Log without trace_id
    logger.info("Request started (no trace_id)")
    
    # Set trace_id and log
    set_trace_id("abc123")
    logger.info("Processing request with trace_id")
    logger.debug("Debug message with trace_id")
    
    # Change trace_id
    set_trace_id("xyz789")
    logger.info("Different request with different trace_id")
    
    # Clear trace_id
    set_trace_id("-")
    logger.info("Request ended (trace_id cleared)")
    
    print("\n✅ Logging example complete!")
