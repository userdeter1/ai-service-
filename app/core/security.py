"""
Core Security Module

Shared authentication and authorization utilities for agents and API endpoints.
Provides role-based access control (RBAC) enforcement.

Usage:
    from app.core.security import require_auth, require_role
    
    # Require authentication
    require_auth(auth_header)  # Raises UnauthorizedError if missing
    
    # Require specific role
    require_role(user_role, ["ADMIN", "OPERATOR"])  # Raises ForbiddenError if not allowed
"""

import logging
from typing import List, Optional

from app.core.errors import UnauthorizedError, ForbiddenError

logger = logging.getLogger(__name__)


# ==================== Authentication ====================

def require_auth(auth_header: Optional[str], allow_empty: bool = False) -> str:
    """
    Require authentication header to be present.
    
    Args:
        auth_header: Authorization header value (e.g., "Bearer <token>")
        allow_empty: If True, empty string is acceptable
        
    Returns:
        The auth_header value
        
    Raises:
        UnauthorizedError: If auth_header is None or empty (when not allowed)
        
    Example:
        >>> from app.core.security import require_auth
        >>> auth = require_auth(request.headers.get("Authorization"))
    """
    if auth_header is None:
        raise UnauthorizedError(
            message="Authentication required",
            details={"reason": "Missing Authorization header"}
        )
    
    if not allow_empty and not auth_header.strip():
        raise UnauthorizedError(
            message="Authentication required",
            details={"reason": "Empty Authorization header"}
        )
    
    return auth_header


def parse_bearer_token(auth_header: Optional[str]) -> Optional[str]:
    """
    Extract bearer token from Authorization header.
    
    Args:
        auth_header: Authorization header value
        
    Returns:
        Token string or None if not a valid bearer token
        
    Example:
        >>> token = parse_bearer_token("Bearer abc123")
        >>> token
        'abc123'
    """
    if not auth_header:
        return None
    
    parts = auth_header.split()
    if len(parts) != 2:
        return None
    
    if parts[0].lower() != "bearer":
        return None
    
    return parts[1]


# ==================== Authorization (RBAC) ====================

def require_role(
    user_role: Optional[str],
    allowed_roles: List[str],
    allow_empty: bool = False
) -> str:
    """
    Require user to have one of the allowed roles.
    
    Args:
        user_role: User's current role
        allowed_roles: List of allowed role names
        allow_empty: If True, None/empty role is acceptable
        
    Returns:
        The user_role value
        
    Raises:
        UnauthorizedError: If user_role is None/empty (when not allowed)
        ForbiddenError: If user_role is not in allowed_roles
        
    Example:
        >>> from app.core.security import require_role
        >>> require_role(user_role, ["ADMIN", "OPERATOR"])
    """
    # Check if role is missing
    if user_role is None or (not allow_empty and not user_role.strip()):
        raise UnauthorizedError(
            message="Role required",
            details={"reason": "Missing user role"}
        )
    
    # Check if role is allowed
    if user_role not in allowed_roles:
        logger.warning(f"Access denied: role '{user_role}' not in {allowed_roles}")
        raise ForbiddenError(
            message="Insufficient permissions",
            details={
                "user_role": user_role,
                "allowed_roles": allowed_roles,
                "reason": f"Role '{user_role}' does not have access to this resource"
            }
        )
    
    return user_role


def has_role(user_role: Optional[str], allowed_roles: List[str]) -> bool:
    """
    Check if user has one of the allowed roles (non-raising version).
    
    Args:
        user_role: User's current role
        allowed_roles: List of allowed role names
        
    Returns:
        True if user_role is in allowed_roles, False otherwise
        
    Example:
        >>> from app.core.security import has_role
        >>> if has_role(user_role, ["ADMIN"]):
        ...     print("Admin access granted")
    """
    if not user_role:
        return False
    
    return user_role in allowed_roles


def is_admin(user_role: Optional[str]) -> bool:
    """
    Check if user has admin role.
    
    Args:
        user_role: User's current role
        
    Returns:
        True if user_role is "ADMIN"
        
    Example:
        >>> from app.core.security import is_admin
        >>> if is_admin(user_role):
        ...     print("Admin user")
    """
    return user_role == "ADMIN"


def is_operator(user_role: Optional[str]) -> bool:
    """
    Check if user has operator role.
    
    Args:
        user_role: User's current role
        
    Returns:
        True if user_role is "OPERATOR"
    """
    return user_role == "OPERATOR"


def is_carrier(user_role: Optional[str]) -> bool:
    """
    Check if user has carrier role.
    
    Args:
        user_role: User's current role
        
    Returns:
        True if user_role is "CARRIER"
    """
    return user_role == "CARRIER"


# ==================== Self-Test ====================

if __name__ == "__main__":
    """
    Self-test for security utilities.
    
    Run: python -m app.core.security
    """
    print("Core Security Self-Test")
    print("=" * 50)
    
    # Test require_auth
    try:
        require_auth(None)
        print("❌ require_auth should raise UnauthorizedError")
    except UnauthorizedError:
        print("✅ require_auth raises UnauthorizedError for None")
    
    auth = require_auth("Bearer abc123")
    print(f"✅ require_auth returns: {auth}")
    
    # Test parse_bearer_token
    token = parse_bearer_token("Bearer abc123")
    print(f"✅ parse_bearer_token: {token}")
    
    # Test require_role
    try:
        require_role("USER", ["ADMIN", "OPERATOR"])
        print("❌ require_role should raise ForbiddenError")
    except ForbiddenError:
        print("✅ require_role raises ForbiddenError for invalid role")
    
    role = require_role("ADMIN", ["ADMIN", "OPERATOR"])
    print(f"✅ require_role returns: {role}")
    
    # Test has_role
    assert has_role("ADMIN", ["ADMIN", "OPERATOR"]) == True
    assert has_role("USER", ["ADMIN", "OPERATOR"]) == False
    print("✅ has_role works correctly")
    
    # Test role checkers
    assert is_admin("ADMIN") == True
    assert is_admin("USER") == False
    assert is_operator("OPERATOR") == True
    assert is_carrier("CARRIER") == True
    print("✅ Role checker functions work correctly")
    
    print("\n✅ All tests passed!")
