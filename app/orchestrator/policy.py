"""
Policy - RBAC Access Control for Orchestrator

Lightweight policy enforcement based on user roles and context.
Returns structured decisions without raising exceptions.

Roles:
- ADMIN: Full access to all features
- OPERATOR: Access to operational features (no admin-only)
- CARRIER: Limited access to own data only

Policy rules:
- booking_status: Requires ownership verification for CARRIER
- carrier_score: ADMIN/OPERATOR full access, CARRIER own data only
- slot_availability: Public (all authenticated+unauthenticated)
- slot_recommendation: Requires authentication
- driver_noshow_risk: ADMIN/OPERATOR only
- All features: Deny unauthenticated for sensitive data
"""

import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ============================================================================
# Policy Configuration
# ============================================================================

ROLE_PERMISSIONS = {
    "ADMIN": {
        "booking_status",
        "slot_availability",
        "slot_recommendation",
        "passage_history",
        "traffic_forecast",
        "anomaly_detection",
        "carrier_score",
        "driver_noshow_risk",
        "blockchain_audit",
        "help",
        "smalltalk",
    },
    "OPERATOR": {
        "booking_status",
        "slot_availability",
        "slot_recommendation",
        "passage_history",
        "traffic_forecast",
        "anomaly_detection",
        "carrier_score",
        "driver_noshow_risk",
        "blockchain_audit",
        "help",
        "smalltalk",
    },
    "CARRIER": {
        "booking_status",  # Own bookings only
        "slot_availability",
        "slot_recommendation",
        "passage_history",  # Own passages only
        "carrier_score",  # Own score only
        "help",
        "smalltalk",
    },
    "UNAUTHENTICATED": {
        "slot_availability",  # Public availability only
        "help",
        "smalltalk",
    },
}

# Intents requiring authentication
REQUIRE_AUTH = {
    "booking_status",
    "carrier_score",
    "slot_recommendation",
    "driver_noshow_risk",
    "passage_history",
    "traffic_forecast",
    "anomaly_detection",
    "blockchain_audit",
}

# Intents requiring ownership verification (for CARRIER role)
REQUIRE_OWNERSHIP = {
    "booking_status",
    "carrier_score",
    "passage_history",
}


@dataclass
class PolicyResult:
    """Policy check result with detailed decision."""
    allowed: bool
    status_code: int  # HTTP status code
    reason: str  # Human-readable reason
    required_role: Optional[str]  # Required role if denied
    safe_to_proceed: bool  # Whether to continue processing
    needs_backend_authorization: bool  # Whether backend must verify ownership
    metadata: Dict[str, Any]  # Additional context


# ============================================================================
# Policy Functions
# ============================================================================

def check_access(
    intent: str,
    context: Dict[str, Any],
    entities: Optional[Dict[str, Any]] = None
) -> Tuple[bool, PolicyResult]:
    """
    Check if user has access to intent based on role and context.
    
    Args:
        intent: Detected intent
        context: Request context (user_role, user_id, auth_header, etc.)
        entities: Extracted entities (for ownership checks)
    
    Returns:
        (ok: bool, policy_result: PolicyResult)
    """
    user_role = context.get("user_role", "UNAUTHENTICATED").upper().strip()
    user_id = context.get("user_id")
    auth_header = context.get("auth_header")
    entities = entities or {}
    
    # Special intents bypass policy
    if intent in ("help", "smalltalk", "unknown"):
        return True, PolicyResult(
            allowed=True,
            status_code=200,
            reason="Public intent",
            required_role=None,
            safe_to_proceed=True,
            needs_backend_authorization=False,
            metadata={"intent": intent}
        )
    
    # Check authentication requirement
    if intent in REQUIRE_AUTH and not auth_header:
        return False, PolicyResult(
            allowed=False,
            status_code=401,
            reason="Authentication required for this feature",
            required_role="authenticated",
            safe_to_proceed=False,
            needs_backend_authorization=False,
            metadata={"intent": intent, "reason": "missing_auth"}
        )
    
    # Check role permissions
    allowed_intents = ROLE_PERMISSIONS.get(user_role, set())
    
    if intent not in allowed_intents:
        return False, PolicyResult(
            allowed=False,
            status_code=403,
            reason=f"Role '{user_role}' does not have permission for '{intent}'",
            required_role="ADMIN" if intent in ("driver_noshow_risk", "anomaly_detection") else "OPERATOR",
            safe_to_proceed=False,
            needs_backend_authorization=False,
            metadata={"intent": intent, "user_role": user_role, "reason": "insufficient_role"}
        )
    
    # Special handling for CARRIER role (ownership checks)
    if user_role == "CARRIER" and intent in REQUIRE_OWNERSHIP:
        ownership_result = _check_ownership(intent, context, entities)
        if not ownership_result["allowed"]:
            return False, PolicyResult(
                allowed=False,
                status_code=403,
                reason=ownership_result["reason"],
                required_role=None,
                safe_to_proceed=False,
                needs_backend_authorization=ownership_result.get("needs_backend_authorization", True),
                metadata={
                    "intent": intent,
                    "user_role": user_role,
                    "reason": "ownership_check_failed",
                    **ownership_result.get("metadata", {})
                }
            )
    
    # Access granted
    return True, PolicyResult(
        allowed=True,
        status_code=200,
        reason="Access granted",
        required_role=None,
        safe_to_proceed=True,
        needs_backend_authorization=False,
        metadata={"intent": intent, "user_role": user_role}
    )


def _check_ownership(
    intent: str,
    context: Dict[str, Any],
    entities: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Check ownership for CARRIER role.
    
    Soft policy: If we can't verify ownership from context alone,
    return needs_backend_authorization=True to let backend enforce.
    """
    user_id = context.get("user_id")
    carrier_id = context.get("carrier_id")  # From JWT/session
    
    if intent == "booking_status":
        # CARRIER can check own bookings
        # We can't verify ownership without calling backend,
        # so mark as needs_backend_authorization
        return {
            "allowed": True,
            "reason": "Ownership check deferred to backend",
            "needs_backend_authorization": True,
            "metadata": {"deferred": "booking_ownership"}
        }
    
    elif intent == "carrier_score":
        # CARRIER can only check own score
        requested_carrier_id = entities.get("carrier_id")
        
        if not requested_carrier_id:
            # No carrier_id specified - assume they want their own
            return {
                "allowed": True,
                "reason": "Checking own carrier score",
                "needs_backend_authorization": False,
                "metadata": {"implicit_ownership": True}
            }
        
        if carrier_id and str(requested_carrier_id) == str(carrier_id):
            # Matches their carrier_id
            return {
                "allowed": True,
                "reason": "Checking own carrier score",
                "needs_backend_authorization": False,
                "metadata": {"verified_ownership": True}
            }
        else:
            # Requesting different carrier
            return {
                "allowed": False,
                "reason": "Cannot access other carriers' scores",
                "needs_backend_authorization": False,
                "metadata": {
                    "requested_carrier": requested_carrier_id,
                    "own_carrier": carrier_id
                }
            }
    
    elif intent == "passage_history":
        # CARRIER can only view own passages
        # Defer to backend for ownership check
        return {
            "allowed": True,
            "reason": "Ownership check deferred to backend",
            "needs_backend_authorization": True,
            "metadata": {"deferred": "passage_ownership"}
        }
    
    # Default: allow but defer to backend
    return {
        "allowed": True,
        "reason": "Access granted",
        "needs_backend_authorization": False,
        "metadata": {}
    }


def get_allowed_intents(user_role: str) -> list:
    """Get list of allowed intents for a role."""
    user_role = user_role.upper().strip()
    return sorted(ROLE_PERMISSIONS.get(user_role, set()))


def requires_auth(intent: str) -> bool:
    """Check if intent requires authentication."""
    return intent in REQUIRE_AUTH


def requires_ownership_check(intent: str, user_role: str) -> bool:
    """Check if intent requires ownership verification for this role."""
    user_role = user_role.upper().strip()
    return user_role == "CARRIER" and intent in REQUIRE_OWNERSHIP


# ============================================================================
# Self-Test
# ============================================================================

if __name__ == "__main__":
    print("Policy - Self Test\n" + "=" * 70)
    
    test_cases = [
        # ADMIN - full access
        ("ADMIN", "booking_status", {"auth_header": "Bearer xxx"}, True),
        ("ADMIN", "carrier_score", {"auth_header": "Bearer xxx"}, True),
        ("ADMIN", "driver_noshow_risk", {"auth_header": "Bearer xxx"}, True),
        
        # OPERATOR - no admin-only features
        ("OPERATOR", "booking_status", {"auth_header": "Bearer xxx"}, True),
        ("OPERATOR", "carrier_score", {"auth_header": "Bearer xxx"}, True),
        ("OPERATOR", "driver_noshow_risk", {"auth_header": "Bearer xxx"}, True),
        
        # CARRIER - limited access
        ("CARRIER", "booking_status", {"auth_header": "Bearer xxx", "carrier_id": "123"}, True),
        ("CARRIER", "slot_availability", {"auth_header": "Bearer xxx"}, True),
        ("CARRIER", "driver_noshow_risk", {"auth_header": "Bearer xxx"}, False),  # Denied
        ("CARRIER", "carrier_score", {"auth_header": "Bearer xxx", "carrier_id": "123"}, True),
        
        # CARRIER - ownership checks
        ("CARRIER", "carrier_score", {"auth_header": "Bearer xxx", "carrier_id": "123"}, True, {"carrier_id": "123"}),  # Own
        ("CARRIER", "carrier_score", {"auth_header": "Bearer xxx", "carrier_id": "123"}, False, {"carrier_id": "456"}),  # Other
        
        # Unauthenticated
        ("UNAUTHENTICATED", "slot_availability", {}, True),  # Public
        ("UNAUTHENTICATED", "booking_status", {}, False),  # Requires auth
        ("UNAUTHENTICATED", "help", {}, True),  # Public
        
        # Missing auth
        ("ADMIN", "booking_status", {}, False),  # No auth header
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        if len(test) == 4:
            role, intent, context, expected = test
            entities = {}
        else:
            role, intent, context, expected, entities = test
        
        context["user_role"] = role
        
        ok, result = check_access(intent, context, entities)
        
        status = "✓" if ok == expected else "✗"
        
        if ok == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} {role:20s} | {intent:25s} | Expected: {expected:5} | Got: {ok:5} | {result.reason[:40]}")
    
    print(f"\n{'=' * 70}")
    print(f"Results: {passed} passed, {failed} failed ({passed/(passed+failed)*100:.1f}% accuracy)")
