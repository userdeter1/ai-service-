"""
Role Constants

Defines user role strings used throughout the system for RBAC enforcement,
policy checks, API guards, and audit logging.

Roles:
- ADMIN: Full system access
- OPERATOR: Operational access (monitoring, bookings, slots)
- CARRIER: Limited access to own data only
- ANON: Unauthenticated/anonymous users (public endpoints only)

Usage:
- Orchestrator: context["user_role"]
- API guards: require_admin(request)
- Policy checks: check_access(intent, context)
- Proofs: proofs["user_role"]
"""

from typing import Optional

# ============================================================================
# Role Constants
# ============================================================================

ADMIN = "ADMIN"
OPERATOR = "OPERATOR"
CARRIER = "CARRIER"
ANON = "ANON"

# All valid roles
ALL_ROLES = {ADMIN, OPERATOR, CARRIER, ANON}

# Default role for missing/invalid input
DEFAULT_ROLE = ANON


# ============================================================================
# Helper Functions
# ============================================================================

def is_valid_role(role: str) -> bool:
    """
    Check if role is valid (case-insensitive).
    
    Args:
        role: Role string to validate
    
    Returns:
        True if valid role, False otherwise
    
    Example:
        >>> is_valid_role("admin")
        True
        >>> is_valid_role("OPERATOR")
        True
        >>> is_valid_role("invalid")
        False
    """
    if not role or not isinstance(role, str):
        return False
    return role.strip().upper() in ALL_ROLES


def normalize_role(role: Optional[str]) -> str:
    """
    Normalize role string to uppercase, return DEFAULT_ROLE if invalid.
    
    Args:
        role: Role string (may be None, mixed case, or invalid)
    
    Returns:
        Normalized uppercase role string, or DEFAULT_ROLE if invalid
    
    Example:
        >>> normalize_role("admin")
        'ADMIN'
        >>> normalize_role("operator")
        'OPERATOR'
        >>> normalize_role(None)
        'ANON'
        >>> normalize_role("invalid")
        'ANON'
    """
    if not role or not isinstance(role, str):
        return DEFAULT_ROLE
    
    normalized = role.strip().upper()
    
    if normalized in ALL_ROLES:
        return normalized
    
    return DEFAULT_ROLE
