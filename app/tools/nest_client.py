"""
NestJS Backend HTTP Client

Provides async interface to NestJS backend APIs for chat persistence.
The NestJS backend is the SINGLE SOURCE OF TRUTH for conversation history.

Functions:
- create_conversation: Create a new conversation
- add_message: Add a message to a conversation
- get_conversation_history: Retrieve conversation with messages
- delete_conversation: Delete a conversation
- aclose_client: Close the HTTP client (call during app shutdown)

All functions forward Authorization headers and handle common HTTP errors.
Uses a module-level singleton AsyncClient for efficient connection pooling.
"""

import os
import logging
from typing import Optional, Dict, Any
import httpx
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration - Read from environment
# ============================================================================

NEST_BACKEND_URL = os.getenv("NEST_BACKEND_URL", "http://localhost:3001")

# Endpoint paths (configurable via env)
NEST_CHAT_CREATE_CONVERSATION_PATH = os.getenv(
    "NEST_CHAT_CREATE_CONVERSATION_PATH", "/chat/conversations"
)
NEST_CHAT_ADD_MESSAGE_PATH = os.getenv(
    "NEST_CHAT_ADD_MESSAGE_PATH", "/chat/conversations/{conversation_id}/messages"
)
NEST_CHAT_GET_HISTORY_PATH = os.getenv(
    "NEST_CHAT_GET_HISTORY_PATH", "/chat/conversations/{conversation_id}"
)
NEST_CHAT_DELETE_CONVERSATION_PATH = os.getenv(
    "NEST_CHAT_DELETE_CONVERSATION_PATH", "/chat/conversations/{conversation_id}"
)

# HTTP client timeout (seconds)
REQUEST_TIMEOUT = float(os.getenv("NEST_CLIENT_TIMEOUT", "30.0"))

# Connection pool limits for scalability
MAX_CONNECTIONS = int(os.getenv("NEST_CLIENT_MAX_CONNECTIONS", "100"))
MAX_KEEPALIVE_CONNECTIONS = int(os.getenv("NEST_CLIENT_MAX_KEEPALIVE", "20"))

logger.info(f"NestJS client configured with backend URL: {NEST_BACKEND_URL}")


# ============================================================================
# Module-level HTTP Client (Singleton with Connection Pooling)
# ============================================================================

_client: Optional[httpx.AsyncClient] = None


def get_client() -> httpx.AsyncClient:
    """
    Get or create the module-level httpx.AsyncClient singleton.
    Initializes client with connection pooling on first call.
    
    Returns:
        Shared httpx.AsyncClient instance
    """
    global _client
    
    # Create client if it doesn't exist or is closed
    if _client is None or _client.is_closed:
        limits = httpx.Limits(
            max_connections=MAX_CONNECTIONS,
            max_keepalive_connections=MAX_KEEPALIVE_CONNECTIONS
        )
        
        _client = httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            limits=limits,
            follow_redirects=False  # Explicit redirect handling
        )
        logger.info("Initialized httpx.AsyncClient with connection pooling")
    
    return _client


async def aclose_client() -> None:
    """
    Close the module-level httpx.AsyncClient gracefully.
    Should be called during FastAPI shutdown (lifespan).
    """
    global _client
    
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        logger.info("Closed httpx.AsyncClient")
        _client = None


# ============================================================================
# Helper Functions
# ============================================================================


def _build_headers(
    auth_header: Optional[str] = None,
    request_id: Optional[str] = None
) -> Dict[str, str]:
    """
    Build request headers with optional Authorization and x-request-id.
    
    Args:
        auth_header: Optional Authorization header value
        request_id: Optional request ID for tracing
    
    Returns:
        Headers dictionary
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    if auth_header:
        headers["Authorization"] = auth_header
    
    if request_id:
        headers["x-request-id"] = request_id
    
    return headers


def _handle_http_error(e: httpx.HTTPStatusError) -> None:
    """
    Map httpx HTTP errors to FastAPI HTTPException with appropriate status codes.
    
    Raises:
        HTTPException with appropriate status code and message
    """
    status_code = e.response.status_code
    
    # Try to extract error message from response
    try:
        error_data = e.response.json()
        error_message = error_data.get("message") or error_data.get("detail") or str(error_data)
    except Exception:
        error_message = e.response.text or f"Backend returned {status_code}"
    
    # Map status codes
    if status_code == 401:
        logger.warning(f"Backend authentication failed: {error_message}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {error_message}"
        )
    elif status_code == 403:
        logger.warning(f"Backend authorization failed: {error_message}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden: {error_message}"
        )
    elif status_code == 404:
        logger.warning(f"Backend resource not found: {error_message}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resource not found: {error_message}"
        )
    elif status_code == 422:
        logger.warning(f"Backend validation error: {error_message}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error: {error_message}"
        )
    elif status_code >= 500:
        logger.error(f"Backend server error ({status_code}): {error_message}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Backend service error: {error_message}"
        )
    else:
        logger.error(f"Unexpected backend error ({status_code}): {error_message}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Backend error: {error_message}"
        )


def _handle_connection_error(e: Exception) -> None:
    """
    Handle connection errors (timeout, network issues, etc.).
    
    Raises:
        HTTPException with 503 status
    """
    logger.error(f"Backend connection error: {type(e).__name__}: {e}")
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Cannot connect to backend service: {type(e).__name__}"
    )


def _normalize_conversation_response(data: Any) -> Dict[str, Any]:
    """
    Normalize backend conversation response to consistent format.
    Handles different response shapes (id vs conversationId, nested data, etc.).
    
    Returns:
        {"id": "...", ...}
    """
    if not isinstance(data, dict):
        return {"id": str(data)} if data else {}
    
    # Extract nested data if present
    nested = {}
    if isinstance(data.get("data"), dict):
        nested = data["data"]
    
    # Try to extract conversation ID from various possible locations (step-by-step)
    conversation_id = data.get("id")
    if not conversation_id:
        conversation_id = data.get("conversationId")
    if not conversation_id:
        conversation_id = nested.get("id")
    if not conversation_id:
        conversation_id = nested.get("conversationId")
    
    # Return normalized structure
    result = {"id": conversation_id}
    
    # Preserve other fields (excluding the ones we already handled)
    for key, value in data.items():
        if key not in ("id", "conversationId", "data"):
            result[key] = value
    
    return result


def _normalize_history_response(data: Any) -> Dict[str, Any]:
    """
    Normalize backend history response to consistent format.
    
    Returns:
        {"id": "...", "messages": [...], ...}
    """
    if not isinstance(data, dict):
        return {"id": None, "messages": []}
    
    # Extract nested data if present
    nested = {}
    if isinstance(data.get("data"), dict):
        nested = data["data"]
    
    # Extract conversation ID (step-by-step to avoid precedence bugs)
    conversation_id = data.get("id")
    if not conversation_id:
        conversation_id = data.get("conversationId")
    if not conversation_id:
        conversation_id = nested.get("id")
    if not conversation_id:
        conversation_id = nested.get("conversationId")
    
    # Extract messages array
    messages = data.get("messages")
    if not messages:
        messages = nested.get("messages")
    if not messages or not isinstance(messages, list):
        messages = []
    
    # Build result
    result = {
        "id": conversation_id,
        "messages": messages
    }
    
    # Preserve other fields
    for key, value in data.items():
        if key not in ("id", "conversationId", "messages", "data"):
            result[key] = value
    
    return result


# ============================================================================
# Public API Functions
# ============================================================================


async def create_conversation(
    user_id: int,
    user_role: str,
    auth_header: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new conversation in the backend.
    
    Args:
        user_id: User ID
        user_role: User role (ADMIN, OPERATOR, CARRIER)
        auth_header: Optional Authorization header to forward
    
    Returns:
        {"id": "conversation_id", ...}
    
    Raises:
        HTTPException: On backend errors
    """
    url = f"{NEST_BACKEND_URL}{NEST_CHAT_CREATE_CONVERSATION_PATH}"
    headers = _build_headers(auth_header)
    payload = {
        "userId": user_id,
        "userRole": user_role
    }
    
    logger.debug(f"Creating conversation for user {user_id} with role {user_role}")
    
    try:
        client = get_client()
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        normalized = _normalize_conversation_response(data)
        logger.info(f"Created conversation: {normalized.get('id')}")
        return normalized
    except httpx.HTTPStatusError as e:
        _handle_http_error(e)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
        _handle_connection_error(e)
    except Exception as e:
        logger.exception(f"Unexpected error creating conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {type(e).__name__}"
        )


async def add_message(
    conversation_id: str,
    role: str,
    content: str,
    intent: Optional[str] = None,
    metadata: Optional[Dict] = None,
    auth_header: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add a message to an existing conversation.
    
    Args:
        conversation_id: Conversation ID
        role: Message role (USER or ASSISTANT)
        content: Message content
        intent: Optional detected intent
        metadata: Optional metadata dict
        auth_header: Optional Authorization header to forward
    
    Returns:
        Created message object
    
    Raises:
        HTTPException: On backend errors
    """
    url = f"{NEST_BACKEND_URL}{NEST_CHAT_ADD_MESSAGE_PATH}".format(
        conversation_id=conversation_id
    )
    headers = _build_headers(auth_header)
    payload = {
        "role": role,
        "content": content
    }
    
    if intent:
        payload["intent"] = intent
    
    if metadata:
        payload["metadata"] = metadata
    
    logger.debug(f"Adding message to conversation {conversation_id} (role={role}, intent={intent})")
    
    try:
        client = get_client()
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Message added to conversation {conversation_id}")
        return data
    except httpx.HTTPStatusError as e:
        _handle_http_error(e)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
        _handle_connection_error(e)
    except Exception as e:
        logger.exception(f"Unexpected error adding message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {type(e).__name__}"
        )


async def get_conversation_history(
    conversation_id: str,
    limit: int = 10,
    offset: int = 0,
    auth_header: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieve conversation history with messages.
    
    Args:
        conversation_id: Conversation ID
        limit: Maximum number of messages to retrieve
        offset: Offset for pagination
        auth_header: Optional Authorization header to forward
    
    Returns:
        {"id": "...", "messages": [...], ...}
    
    Raises:
        HTTPException: On backend errors
    """
    url = f"{NEST_BACKEND_URL}{NEST_CHAT_GET_HISTORY_PATH}".format(
        conversation_id=conversation_id
    )
    headers = _build_headers(auth_header)
    params = {
        "limit": limit,
        "offset": offset
    }
    
    logger.debug(f"Fetching conversation {conversation_id} (limit={limit}, offset={offset})")
    
    try:
        client = get_client()
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        normalized = _normalize_history_response(data)
        logger.info(f"Retrieved conversation {conversation_id} with {len(normalized.get('messages', []))} messages")
        return normalized
    except httpx.HTTPStatusError as e:
        _handle_http_error(e)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
        _handle_connection_error(e)
    except Exception as e:
        logger.exception(f"Unexpected error fetching conversation history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {type(e).__name__}"
        )


async def delete_conversation(
    conversation_id: str,
    auth_header: Optional[str] = None
) -> Dict[str, Any]:
    """
    Delete a conversation from the backend.
    
    Args:
        conversation_id: Conversation ID
        auth_header: Optional Authorization header to forward
    
    Returns:
        Backend response (usually success confirmation)
    
    Raises:
        HTTPException: On backend errors
    """
    url = f"{NEST_BACKEND_URL}{NEST_CHAT_DELETE_CONVERSATION_PATH}".format(
        conversation_id=conversation_id
    )
    headers = _build_headers(auth_header)
    
    logger.debug(f"Deleting conversation {conversation_id}")
    
    try:
        client = get_client()
        response = await client.delete(url, headers=headers)
        response.raise_for_status()
        
        # Some backends return 204 No Content
        if response.status_code == 204:
            logger.info(f"Deleted conversation {conversation_id}")
            return {"success": True, "id": conversation_id}
        
        data = response.json()
        logger.info(f"Deleted conversation {conversation_id}")
        return data
    except httpx.HTTPStatusError as e:
        _handle_http_error(e)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
        _handle_connection_error(e)
    except Exception as e:
        logger.exception(f"Unexpected error deleting conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {type(e).__name__}"
        )
