"""
Admin authentication and authorization module.

Provides role-based access control for administrative endpoints.
"""

from enum import Enum
from functools import wraps
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import settings
from app.core.security import verify_jwt_token
from app.log.logging import logger

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


class AdminRole(str, Enum):
    """Admin role levels with increasing permissions."""

    VIEWER = "viewer"  # Read-only access to dashboard and analytics
    OPERATOR = "operator"  # Can manage queues, trigger jobs
    ADMIN = "admin"  # Full access including user management


# Role hierarchy (higher roles include lower permissions)
ROLE_HIERARCHY = {
    AdminRole.VIEWER: 0,
    AdminRole.OPERATOR: 1,
    AdminRole.ADMIN: 2,
}


class AdminUser:
    """Represents an authenticated admin user."""

    def __init__(
        self,
        user_id: str,
        email: str | None = None,
        admin_role: AdminRole = AdminRole.VIEWER,
        is_admin: bool = False,
    ):
        self.user_id = user_id
        self.email = email
        self.admin_role = admin_role
        self.is_admin = is_admin

    def has_role(self, required_role: AdminRole) -> bool:
        """Check if user has at least the required role level."""
        if not self.is_admin:
            return False
        return ROLE_HIERARCHY.get(self.admin_role, 0) >= ROLE_HIERARCHY.get(
            required_role, 0
        )


async def get_admin_user(token: str = Depends(oauth2_scheme)) -> AdminUser:
    """
    Extract and validate admin user from JWT token.

    The token payload should contain:
    - id: User ID
    - email: User email (optional)
    - is_admin: Boolean indicating admin status
    - admin_role: One of 'viewer', 'operator', 'admin'
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = verify_jwt_token(token)
        user_id = payload.get("id")
        if user_id is None:
            raise credentials_exception

        # Extract admin info from token
        is_admin = payload.get("is_admin", False)
        admin_role_str = payload.get(settings.admin_role_claim, "viewer")

        # Validate role
        try:
            admin_role = AdminRole(admin_role_str)
        except ValueError:
            admin_role = AdminRole.VIEWER

        return AdminUser(
            user_id=str(user_id),
            email=payload.get("email"),
            admin_role=admin_role,
            is_admin=is_admin,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Admin auth failed: {e}")
        raise credentials_exception


def require_admin(user: AdminUser = Depends(get_admin_user)) -> AdminUser:
    """Dependency that requires admin access (any role)."""
    if not settings.admin_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin features are not enabled",
        )

    if not user.is_admin:
        logger.warning(
            "Non-admin user attempted admin access",
            event_type="admin_access_denied",
            user_id=user.user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return user


def require_admin_role(min_role: AdminRole):
    """
    Dependency factory that requires a minimum admin role.

    Usage:
        @router.get("/admin/dashboard")
        async def dashboard(user: AdminUser = Depends(require_admin_role(AdminRole.VIEWER))):
            pass

        @router.post("/admin/queues/{queue}/purge")
        async def purge_queue(user: AdminUser = Depends(require_admin_role(AdminRole.OPERATOR))):
            pass
    """

    async def verify_role(user: AdminUser = Depends(require_admin)) -> AdminUser:
        if not user.has_role(min_role):
            logger.warning(
                "Insufficient admin role",
                event_type="admin_role_denied",
                user_id=user.user_id,
                required_role=min_role.value,
                user_role=user.admin_role.value,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {min_role.value} role or higher",
            )
        return user

    return verify_role


def audit_admin_action(action: str):
    """
    Decorator to audit admin actions.

    Usage:
        @audit_admin_action("user_blocked")
        async def block_user(user_id: str, admin: AdminUser):
            pass
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract admin user from kwargs
            admin_user = kwargs.get("admin") or kwargs.get("user")

            result = await func(*args, **kwargs)

            # Log the action
            if admin_user and isinstance(admin_user, AdminUser):
                logger.info(
                    f"Admin action: {action}",
                    event_type="admin_action",
                    action=action,
                    admin_id=admin_user.user_id,
                    admin_role=admin_user.admin_role.value,
                )

            return result

        return wrapper

    return decorator
