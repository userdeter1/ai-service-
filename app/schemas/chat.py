"""
Chat Schemas

Request/response models for chat API endpoints.
Matches app/api/chat.py fallback ChatRequest/ChatResponse structure.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.base import Proofs


class ChatRequest(BaseModel):
    """
    Chat request payload.
    
    Required:
    - message: User's message/query
    - user_id: User identifier
    - user_role: User role (ADMIN/OPERATOR/CARRIER)
    
    Optional:
    - conversation_id: Existing conversation ID for continuity
    - context: Additional context dict
    """
    message: str = Field(..., description="User message/query", min_length=1)
    user_id: int = Field(..., description="User ID", gt=0)
    user_role: str = Field(..., description="User role: ADMIN, OPERATOR, CARRIER")
    conversation_id: Optional[str] = Field(None, description="Existing conversation ID")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    
    model_config = ConfigDict(extra="allow")


class ChatHistoryMessage(BaseModel):
    """Single message in chat history."""
    role: str = Field(..., description="Message role (USER/ASSISTANT)")
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = Field(None, description="Message timestamp (ISO format)")
    
    model_config = ConfigDict(extra="allow")


class ChatResponse(BaseModel):
    """
    Chat response payload.
    
    Returns:
    - conversation_id: Conversation identifier
    - message: AI assistant's response
    - intent: Detected intent (optional)
    - entities: Extracted entities (optional)
    - agent: Agent that handled request (optional)
    - data: Additional response data (optional)
    - proofs: Tracing information (optional)
    """
    conversation_id: str = Field(..., description="Conversation ID")
    message: str = Field(..., description="AI assistant's response")
    intent: Optional[str] = Field(None, description="Detected intent")
    entities: Optional[Dict[str, Any]] = Field(None, description="Extracted entities")
    agent: Optional[str] = Field(None, description="Agent that handled request")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional response data")
    proofs: Optional[Proofs] = Field(None, description="Tracing/proof information")
    
    model_config = ConfigDict(extra="allow")


class ChatHistoryResponse(BaseModel):
    """
    Chat history response.
    
    Returns conversation history from backend.
    """
    conversation_id: str = Field(..., description="Conversation ID")
    messages: List[ChatHistoryMessage] = Field(..., description="Message history")
    total: int = Field(..., description="Total message count")
    
    model_config = ConfigDict(extra="allow")
