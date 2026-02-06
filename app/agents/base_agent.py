"""
Base Agent Class

All specialized agents inherit from this base class.
Defines common interface and behavior for agent execution.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Base class for all specialized agents.
    
    Provides:
    - Standard execute() method that orchestrator calls
    - run() method that child classes must implement
    - Helper methods for response formatting
    """

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point called by orchestrator.
        Wraps run() with standard error handling.
        
        Args:
            context: Dictionary containing:
                - message: str - User's query
                - entities: Dict[str, Any] - Extracted entities
                - history: List[Dict] - Normalized conversation history
                - user_role: str - User role (ADMIN/OPERATOR/CARRIER)
                - user_id: int - User identifier
                - trace_id: str - Request trace ID
                - auth_header: Optional[str] - Authorization header
                - (optional) other context fields
        
        Returns:
            Dict with keys: message, data, proofs
        """
        try:
            return await self.run(context)
        except Exception as e:
            logger.exception(f"{self.__class__.__name__} execution failed: {e}")
            trace_id = context.get("trace_id", "unknown")
            return self.error_response(
                message="I encountered an unexpected error. Please try again.",
                trace_id=trace_id,
                error_type=type(e).__name__
            )

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Core business logic - must be implemented by child classes.
        
        Args:
            context: Full context dictionary from orchestrator
        
        Returns:
            Structured response with message, data, and proofs
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement run() method")

    # ========================================================================
    # Helper Methods for Response Formatting
    # ========================================================================

    def success_response(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        **extra_proofs
    ) -> Dict[str, Any]:
        """
        Create a successful response.
        
        Args:
            message: User-facing success message
            data: Optional data payload
            trace_id: Optional trace ID
            **extra_proofs: Additional fields to include in proofs
        
        Returns:
            Structured success response
        """
        proofs = {}
        if trace_id:
            proofs["trace_id"] = trace_id
        proofs.update(extra_proofs)
        
        return {
            "message": message,
            "data": data,
            "proofs": proofs if proofs else None
        }

    def validation_error(
        self,
        message: str,
        suggestion: str,
        missing_field: Optional[str] = None,
        example: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a validation error response.
        
        Args:
            message: User-facing error message
            suggestion: Helpful suggestion for the user
            missing_field: Optional field that is missing
            example: Optional example of valid input
            trace_id: Optional trace ID
        
        Returns:
            Structured validation error response
        """
        data = {
            "error": "validation_failed",
            "suggestion": suggestion
        }
        
        if missing_field:
            data["missing_field"] = missing_field
        
        if example:
            data["example"] = example
        
        proofs = {}
        if trace_id:
            proofs["trace_id"] = trace_id
        proofs["validation"] = "failed"
        
        return {
            "message": f"{message}\n\n{suggestion}",
            "data": data,
            "proofs": proofs
        }

    def error_response(
        self,
        message: str,
        trace_id: Optional[str] = None,
        error_type: Optional[str] = None,
        **extra_data
    ) -> Dict[str, Any]:
        """
        Create an error response.
        
        Args:
            message: User-facing error message
            trace_id: Optional trace ID
            error_type: Optional error type (for debugging)
            **extra_data: Additional fields to include in data
        
        Returns:
            Structured error response
        """
        data = {"error": "execution_failed"}
        
        if error_type:
            data["error_type"] = error_type
        
        data.update(extra_data)
        
        proofs = {}
        if trace_id:
            proofs["trace_id"] = trace_id
        proofs["status"] = "failed"
        
        return {
            "message": message,
            "data": data,
            "proofs": proofs
        }

    # ========================================================================
    # Helper Methods for Context Extraction
    # ========================================================================

    def get_trace_id(self, context: Dict[str, Any]) -> str:
        """Extract trace_id from context, with fallback."""
        return context.get("trace_id", "unknown")

    def get_entities(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract entities from context, with fallback."""
        return context.get("entities", {})

    def get_auth_header(self, context: Dict[str, Any]) -> Optional[str]:
        """
        Extract Authorization header from context.
        Tries multiple possible field names.
        """
        return (
            context.get("auth_header") or
            context.get("authorization") or
            context.get("Authorization")
        )

    def get_user_role(self, context: Dict[str, Any]) -> str:
        """Extract user_role from context, with fallback."""
        return context.get("user_role", "UNKNOWN")

    def get_user_id(self, context: Dict[str, Any]) -> Optional[int]:
        """Extract user_id from context."""
        return context.get("user_id")

    def get_message(self, context: Dict[str, Any]) -> str:
        """Extract user message from context, with fallback."""
        return context.get("message", "")

    def get_history(self, context: Dict[str, Any]) -> list:
        """Extract conversation history from context, with fallback."""
        return context.get("history", [])
