"""
Orchestrator - Multi-Agent Message Router

Hierarchical orchestrator that:
1. Detects user intent from natural language
2. Extracts entities (booking refs, dates, terminals, etc.)
3. Enforces RBAC based on user role
4. Routes to specialized agents via registry
5. Returns structured responses with tracing
"""

import re
import uuid
import logging
import inspect
from typing import Dict, List, Any, Optional, Callable, Type

logger = logging.getLogger(__name__)

# ============================================================================
# RBAC Configuration
# ============================================================================

ROLE_PERMISSIONS = {
    "ADMIN": {
        "booking_status",
        "slot_availability",
        "passage_history",
        "traffic_forecast",
        "anomaly_detection",
        "carrier_score",
        "blockchain_audit",
        "help",
    },
    "OPERATOR": {
        "booking_status",
        "slot_availability",
        "passage_history",
        "anomaly_detection",
        "carrier_score",
        "blockchain_audit",
        "help",
    },
    "CARRIER": {
        "booking_status",
        "slot_availability",
        "passage_history",
        "help",
    },
}

# ============================================================================
# Intent Patterns (Priority Ordered)
# ============================================================================

INTENT_PATTERNS = [
    # HIGHEST PRIORITY: Help/Greetings
    ("help", [
        r"\b(help|assist|what can|how to|guide)\b",
        r"^(hi|hello|hey|bonjour|salam)(\s|$)",
    ]),
    
    # HIGH PRIORITY: Blockchain (takes precedence over booking_status even with REF)
    ("blockchain_audit", [
        r"\b(blockchain|proof|verify|audit|trace)\b",
        r"\b(prove|verify)\b.*\b(booking|transaction)\b",
    ]),
    
    # HIGH PRIORITY: Anomaly (takes precedence over booking_status)
    ("anomaly_detection", [
        r"\b(anomaly|anomalies|unusual|suspicious|no-show|delay)\b",
        r"\b(detect|find|show)\b.*\b(anomaly|anomalies|issue)\b",
        r"\b(recurrent|frequent)\b.*\b(no-show|delay|problem)\b",
    ]),
    
    # MEDIUM PRIORITY: Other specialized intents
    ("carrier_score", [
        r"\b(carrier|driver|company)\b.*\b(score|rating|reliability|performance)\b",
        r"\b(score|rating|reliability)\b.*\b(carrier|driver)\b",
        r"\b(how reliable|performance of)\b",
    ]),
    
    ("traffic_forecast", [
        r"\b(traffic|congestion)\b.*\b(forecast|predict|tomorrow|future)\b",
        r"\b(tomorrow|next|future)\b.*\b(traffic|congestion|busy)\b",
        r"\b(predict|forecast)\b.*\b(traffic|load)\b",
    ]),
    
    ("passage_history", [
        r"\b(passage|entry|entries|truck|vehicle)\b.*\b(history|yesterday|past|previous)\b",
        r"\b(show|list|get)\b.*\b(passage|entry|truck)\b",
        r"\byesterday.*\b(passage|truck|entry)\b",
    ]),
    
    ("slot_availability", [
        r"\b(available|availability|free|open)\b.*\b(slot|time|appointment)\b",
        r"\b(slot|time|appointment)\b.*\b(available|free|open)\b",
        r"\b(book|reserve|schedule)\b.*\b(slot|time)\b",
    ]),
    
    # LOWER PRIORITY: Generic booking status
    ("booking_status", [
        r"\b(status|track|where|check|find|locate)\b.*\b(booking|reservation|ref|reference)\b",
        r"\b(booking|reservation|ref|reference)\b.*\b(status|track|where|check)\b",
        r"\bREF\d+\b",
    ]),
]

# ============================================================================
# Entity Extraction Patterns (Improved)
# ============================================================================

ENTITY_PATTERNS = {
    "booking_ref": r"\b(REF|ref|Ref)[-\s]?(\d{3,})\b",
    "plate": r"\b([A-Z]{1,3}[-\s]?\d{3,4}[-\s]?[A-Z]{1,3})\b",
    "terminal": r"\b(Terminal|terminal|TERMINAL)\s+([A-Za-z0-9]+)\b",
    "gate": r"\b(Gate|gate|GATE)\s+([A-Za-z0-9]+)\b",
    "date_today": r"\b(today|now|current)\b",
    "date_tomorrow": r"\b(tomorrow|next day)\b",
    "date_yesterday": r"\b(yesterday|last day)\b",
}

FOLLOW_UP_KEYWORDS = r"\b(and|what about|then|also|too|same|yesterday|tomorrow|today|next|previous)\b"

# ============================================================================
# Orchestrator Class
# ============================================================================


class Orchestrator:
    """
    Hierarchical multi-agent orchestrator for smart port chatbot.
    """

    def __init__(self):
        self.agent_registry: Dict[str, Optional[Type]] = {}
        self._build_agent_registry()
        available_count = sum(1 for a in self.agent_registry.values() if a)
        logger.info(f"Orchestrator initialized with {available_count}/{len(self.agent_registry)} agents available")

    def _build_agent_registry(self):
        """Build agent registry with safe imports (lazy, hot-reload friendly)."""
        
        try:
            from app.agents.booking_agent import BookingAgent
            self.agent_registry["booking_status"] = BookingAgent
        except ImportError:
            self.agent_registry["booking_status"] = None

        try:
            from app.agents.slot_agent import SlotAgent
            self.agent_registry["slot_availability"] = SlotAgent
        except ImportError:
            self.agent_registry["slot_availability"] = None

        try:
            from app.agents.passage_history_agent import PassageHistoryAgent
            self.agent_registry["passage_history"] = PassageHistoryAgent
        except ImportError:
            self.agent_registry["passage_history"] = None

        try:
            from app.agents.traffic_agent import TrafficAgent
            self.agent_registry["traffic_forecast"] = TrafficAgent
        except ImportError:
            self.agent_registry["traffic_forecast"] = None

        try:
            from app.agents.anomaly_agent import AnomalyAgent
            self.agent_registry["anomaly_detection"] = AnomalyAgent
        except ImportError:
            self.agent_registry["anomaly_detection"] = None

        try:
            from app.agents.carrier_score_agent import CarrierScoreAgent
            self.agent_registry["carrier_score"] = CarrierScoreAgent
        except ImportError:
            self.agent_registry["carrier_score"] = None

        try:
            from app.agents.blockchain_audit_agent import BlockchainAuditAgent
            self.agent_registry["blockchain_audit"] = BlockchainAuditAgent
        except ImportError:
            self.agent_registry["blockchain_audit"] = None

    async def handle_message(
        self,
        message: str,
        history: List[Dict[str, Any]],
        user_role: str,
        user_id: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Main entry point for message processing.

        Args:
            message: User's natural language query
            history: Normalized conversation history
            user_role: ADMIN | OPERATOR | CARRIER
            user_id: User identifier
            context: Optional contextual data

        Returns:
            {
                "message": str,
                "intent": str | None,
                "data": dict | None,
                "proofs": dict | None
            }
        """
        trace_id = str(uuid.uuid4())
        decision_path = []

        # Normalize user_role at the beginning
        user_role = user_role.strip().upper()

        try:
            # Step 1: Detect intent (priority-ordered)
            intent = self._detect_intent(message, history)
            decision_path.append(f"intent:{intent}")

            # Step 2: Extract entities
            entities = self._extract_entities(message)
            decision_path.append(f"entities:{len(entities)}")

            # Log minimal info (no full message for privacy)
            logger.info(f"[{trace_id[:8]}] intent={intent} role={user_role}")

            # Step 3: Handle special intents BEFORE RBAC (help and unknown bypass RBAC)
            if intent == "help":
                return self._handle_help(user_role, trace_id, decision_path)

            if intent == "unknown":
                return self._handle_unknown(message, user_role, trace_id, decision_path)

            # Step 4: RBAC check (only for business intents)
            if not self._rbac_check(intent, user_role):
                decision_path.append("rbac_denied")
                return {
                    "message": f"Sorry, the '{intent}' feature is not available for your role ({user_role}).",
                    "intent": "forbidden",
                    "data": {
                        "requested_intent": intent,
                        "user_role": user_role,
                        "allowed_intents": sorted(ROLE_PERMISSIONS.get(user_role, set())),
                    },
                    "proofs": {
                        "trace_id": trace_id,
                        "decision_path": decision_path,
                    },
                }

            decision_path.append("rbac_granted")

            # Step 5: Route to agent
            agent_class = self.agent_registry.get(intent)

            if not agent_class:
                decision_path.append("agent_not_implemented")
                return {
                    "message": f"The '{intent}' feature is planned but not yet implemented. It will be available soon!",
                    "intent": "not_implemented",
                    "data": {
                        "planned_intent": intent,
                        "entities": entities,
                        "suggestion": "Please check back later or contact support.",
                    },
                    "proofs": {
                        "trace_id": trace_id,
                        "decision_path": decision_path,
                    },
                }

            decision_path.append(f"agent:{agent_class.__name__}")

            # Step 6: Execute agent
            result = await self._execute_agent(
                agent_class=agent_class,
                message=message,
                entities=entities,
                history=history,
                user_role=user_role,
                user_id=user_id,
                trace_id=trace_id,
                context=context or {},
                decision_path=decision_path,
            )

            # Add orchestrator metadata
            result.setdefault("intent", intent)
            result.setdefault("proofs", {})
            result["proofs"]["trace_id"] = trace_id
            result["proofs"]["decision_path"] = decision_path

            return result

        except Exception as e:
            logger.exception(f"[{trace_id[:8]}] Orchestrator error: {e}")
            return {
                "message": "I encountered an unexpected error. Please try again or contact support.",
                "intent": "orchestrator_error",
                "data": {
                    "error_type": type(e).__name__,
                },
                "proofs": {
                    "trace_id": trace_id,
                    "decision_path": decision_path,
                },
            }

    async def handle(self, *args, **kwargs) -> Dict[str, Any]:
        """Alias for handle_message."""
        return await self.handle_message(*args, **kwargs)

    def _detect_intent(self, message: str, history: List[Dict[str, Any]]) -> str:
        """
        Detect user intent from message using priority-ordered patterns.
        Uses conversation history for follow-up detection.
        """
        message_lower = message.lower()

        # Check for follow-up patterns
        is_short = len(message.split()) <= 4
        has_follow_up_keyword = bool(re.search(FOLLOW_UP_KEYWORDS, message_lower, re.IGNORECASE))

        # Priority-ordered intent matching
        for intent, patterns in INTENT_PATTERNS:
            for pattern in patterns:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    return intent

        # If unknown and looks like follow-up, try to reuse last intent
        if is_short or has_follow_up_keyword:
            last_intent = self._get_last_intent(history)
            if last_intent and last_intent != "unknown":
                return last_intent

        return "unknown"

    def _get_last_intent(self, history: List[Dict[str, Any]]) -> Optional[str]:
        """Extract last non-unknown intent from history."""
        for msg in reversed(history):
            if isinstance(msg, dict):
                # Check top-level intent first (current backend schema)
                # Fallback to metadata.intent for future-proofing against schema evolution
                intent = msg.get("intent") or msg.get("metadata", {}).get("intent")
                if intent and intent not in ("unknown", "help", "forbidden", "not_implemented"):
                    return intent
        return None

    def _extract_entities(self, message: str) -> Dict[str, Any]:
        """
        Extract entities from message using improved regex patterns.
        Supports multiple matches for booking_ref and normalized output.
        """
        entities: Dict[str, Any] = {}

        # Booking references (multiple, normalized with prefix)
        booking_refs = []
        for match in re.finditer(ENTITY_PATTERNS["booking_ref"], message, re.IGNORECASE):
            prefix = match.group(1).upper()
            digits = match.group(2)
            booking_refs.append(f"{prefix}{digits}")
        if booking_refs:
            entities["booking_ref"] = booking_refs[0] if len(booking_refs) == 1 else booking_refs

        # License plate (improved pattern - requires digits, safer)
        match = re.search(ENTITY_PATTERNS["plate"], message, re.IGNORECASE)
        if match:
            entities["plate"] = match.group(1).strip()

        # Terminal (extract identifier and full string)
        match = re.search(ENTITY_PATTERNS["terminal"], message, re.IGNORECASE)
        if match:
            entities["terminal"] = match.group(2).strip().upper()
            entities["terminal_full"] = match.group(0).strip()

        # Gate (extract identifier and full string)
        match = re.search(ENTITY_PATTERNS["gate"], message, re.IGNORECASE)
        if match:
            entities["gate"] = match.group(2).strip().upper()
            entities["gate_full"] = match.group(0).strip()

        # Date keywords (booleans)
        for entity_name, pattern in ENTITY_PATTERNS.items():
            if entity_name.startswith("date_"):
                if re.search(pattern, message, re.IGNORECASE):
                    entities[entity_name] = True

        return entities

    def _rbac_check(self, intent: str, user_role: str) -> bool:
        """Check if user role has permission for intent."""
        allowed_intents = ROLE_PERMISSIONS.get(user_role, set())
        return intent in allowed_intents

    async def _execute_agent(
        self,
        agent_class: Type,
        message: str,
        entities: Dict[str, Any],
        history: List[Dict[str, Any]],
        user_role: str,
        user_id: int,
        trace_id: str,
        context: Dict[str, Any],
        decision_path: List[str],
    ) -> Dict[str, Any]:
        """
        Execute agent with flexible method signatures and sync/async support.
        """
        try:
            agent = agent_class()
            decision_path.append("agent_instantiated")

            # Build context dict
            agent_context = {
                "message": message,
                "entities": entities,
                "history": history,
                "user_role": user_role,
                "user_id": user_id,
                "trace_id": trace_id,
                **context,
            }

            # Find agent method
            method = None
            for method_name in ("execute", "handle", "process"):
                if hasattr(agent, method_name):
                    method = getattr(agent, method_name)
                    break

            if not method:
                decision_path.append("agent_no_method")
                return {
                    "message": f"Agent is not properly configured.",
                    "data": {"error": "Agent has no execute/handle/process method"},
                }

            # Try calling with dict context first
            try:
                if inspect.iscoroutinefunction(method):
                    result = await method(agent_context)
                else:
                    result = method(agent_context)
                    if inspect.isawaitable(result):
                        result = await result
            except TypeError:
                # Fallback: try keyword args
                try:
                    if inspect.iscoroutinefunction(method):
                        result = await method(
                            message=message,
                            entities=entities,
                            history=history,
                            user_role=user_role,
                            user_id=user_id,
                            trace_id=trace_id,
                            context=context,
                        )
                    else:
                        result = method(
                            message=message,
                            entities=entities,
                            history=history,
                            user_role=user_role,
                            user_id=user_id,
                            trace_id=trace_id,
                            context=context,
                        )
                        if inspect.isawaitable(result):
                            result = await result
                except TypeError as e:
                    decision_path.append(f"agent_call_failed:{type(e).__name__}")
                    return {
                        "message": "Agent configuration error.",
                        "data": {"error": "Agent method signature mismatch"},
                    }

            decision_path.append("agent_executed")

            # Ensure result is dict
            if not isinstance(result, dict):
                result = {"message": str(result), "data": None}

            return result

        except Exception as e:
            logger.exception(f"[{trace_id[:8]}] Agent execution failed: {e}")
            decision_path.append(f"agent_failed:{type(e).__name__}")
            return {
                "message": "I encountered an error processing your request. Please try again.",
                "data": {"error_type": type(e).__name__},
            }

    def _handle_help(self, user_role: str, trace_id: str, decision_path: List[str]) -> Dict[str, Any]:
        """Generate context-aware help message."""
        decision_path.append("help_generated")

        allowed_features = sorted(ROLE_PERMISSIONS.get(user_role, set()) - {"help"})

        help_messages = {
            "booking_status": "Check the status of your bookings (e.g., 'What's the status of REF123?')",
            "slot_availability": "Find available time slots (e.g., 'Is there availability tomorrow at Terminal A?')",
            "passage_history": "View past truck passages (e.g., 'Show me yesterday's entries')",
            "traffic_forecast": "Get traffic predictions (e.g., 'What's tomorrow's traffic forecast?')",
            "anomaly_detection": "Detect unusual patterns (e.g., 'Show me recurrent no-shows')",
            "carrier_score": "Check carrier reliability (e.g., 'What's the score for carrier X?')",
            "blockchain_audit": "Verify blockchain proofs (e.g., 'Prove booking REF123')",
        }

        features_list = "\n".join([f"• {help_messages.get(f, f)}" for f in allowed_features if f in help_messages])

        return {
            "message": f"Hello! I'm your Smart Port AI assistant. Here's what I can help you with:\n\n{features_list}\n\nJust ask me in natural language!",
            "intent": "help",
            "data": {
                "user_role": user_role,
                "available_features": allowed_features,
            },
            "proofs": {
                "trace_id": trace_id,
                "decision_path": decision_path,
            },
        }

    def _handle_unknown(self, message: str, user_role: str, trace_id: str, decision_path: List[str]) -> Dict[str, Any]:
        """Handle unrecognized intents."""
        decision_path.append("unknown_intent")

        suggestions = [
            "Check booking status: 'What's the status of REF123?'",
            "Find available slots: 'Is there availability tomorrow?'",
            "View passage history: 'Show yesterday's truck entries'",
        ]

        return {
            "message": f"I'm not sure I understood your request. Here are some things you can ask me:\n\n" + "\n".join(f"• {s}" for s in suggestions[:3]),
            "intent": "unknown",
            "data": {
                "suggestions": suggestions,
            },
            "proofs": {
                "trace_id": trace_id,
                "decision_path": decision_path,
            },
        }
