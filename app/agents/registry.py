"""
Agent Registry

Central registry for all agents. Provides lazy instantiation and lookup.
Used by orchestrator to route intents to appropriate agents.

DO NOT import orchestrator here to avoid circular dependencies.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Lazy-loaded agent instances (singletons)
_agent_instances: Dict[str, Any] = {}


# ============================================================================
# Agent Registry - Maps agent names to classes
# ============================================================================

def _get_agent_classes() -> Dict[str, type]:
    """
    Dynamically import agent classes to avoid import errors if some don't exist yet.
    Returns mapping of agent_name -> agent_class.
    """
    registry = {}
    
    # Import existing agents
    try:
        from app.agents.booking_agent import BookingAgent
        registry["BookingAgent"] = BookingAgent
    except ImportError as e:
        logger.warning(f"Could not import BookingAgent: {e}")
    
    try:
        from app.agents.slot_agent import SlotAgent
        registry["SlotAgent"] = SlotAgent
    except ImportError as e:
        logger.warning(f"Could not import SlotAgent: {e}")
    
    try:
        from app.agents.carrier_score_agent import CarrierScoreAgent
        registry["CarrierScoreAgent"] = CarrierScoreAgent
    except ImportError as e:
        logger.warning(f"Could not import CarrierScoreAgent: {e}")
    
    try:
        from app.agents.traffic_agent import TrafficAgent
        registry["TrafficAgent"] = TrafficAgent
    except ImportError as e:
        logger.warning(f"Could not import TrafficAgent: {e}")
    
    try:
        from app.agents.anomaly_agent import AnomalyAgent
        registry["AnomalyAgent"] = AnomalyAgent
    except ImportError as e:
        logger.warning(f"Could not import AnomalyAgent: {e}")
    
    try:
        from app.agents.recommendation_agent import RecommendationAgent
        registry["RecommendationAgent"] = RecommendationAgent
    except ImportError as e:
        logger.warning(f"Could not import RecommendationAgent: {e}")
    
    try:
        from app.agents.blockchain_audit_agent import BlockchainAuditAgent
        registry["BlockchainAuditAgent"] = BlockchainAuditAgent
    except ImportError as e:
        logger.warning(f"Could not import BlockchainAuditAgent: {e}")
    
    try:
        from app.agents.analytics_agent import AnalyticsAgent
        registry["AnalyticsAgent"] = AnalyticsAgent
    except ImportError as e:
        logger.warning(f"Could not import AnalyticsAgent: {e}")
    
    return registry


# Build registry at module load time
AGENT_REGISTRY = _get_agent_classes()


# ============================================================================
# Public API
# ============================================================================

def get_agent(agent_name: str) -> Any:
    """
    Get agent instance by name. Uses lazy singleton pattern.
    
    Args:
        agent_name: Name of agent class (e.g. "BookingAgent", "SlotAgent")
    
    Returns:
        Agent instance
    
    Raises:
        ValueError: If agent_name not found in registry
    
    Example:
        >>> agent = get_agent("BookingAgent")
        >>> result = await agent.execute(context)
    """
    if agent_name not in AGENT_REGISTRY:
        available = list(AGENT_REGISTRY.keys())
        raise ValueError(
            f"Unknown agent: {agent_name}. Available agents: {', '.join(available)}"
        )
    
    # Return cached instance if exists
    if agent_name in _agent_instances:
        return _agent_instances[agent_name]
    
    # Create new instance and cache
    agent_class = AGENT_REGISTRY[agent_name]
    agent_instance = agent_class()
    _agent_instances[agent_name] = agent_instance
    
    logger.info(f"Initialized agent: {agent_name}")
    return agent_instance


def list_agents() -> Dict[str, Dict[str, Any]]:
    """
    List all available agents and their status.
    
    Returns:
        Dict mapping agent_name -> {class, loaded}
    
    Example:
        >>> agents = list_agents()
        >>> print(agents)
        {
            "BookingAgent": {"class": "BookingAgent", "loaded": True},
            "SlotAgent": {"class": "SlotAgent", "loaded": True},
            ...
        }
    """
    result = {}
    
    for agent_name, agent_class in AGENT_REGISTRY.items():
        result[agent_name] = {
            "class": agent_class.__name__,
            "loaded": agent_name in _agent_instances
        }
    
    return result


def clear_instances():
    """
    Clear all cached agent instances. Useful for testing.
    """
    global _agent_instances
    _agent_instances.clear()
    logger.info("Cleared all agent instances")
