"""
Admin dashboard API router.

Provides endpoints for:
- Dashboard summary and system overview
- Application analytics
- User analytics and management
- Error analytics
- Queue management
- Audit log
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.admin_auth import (
    AdminRole,
    AdminUser,
    require_admin,
    require_admin_role,
)
from app.core.config import settings
from app.log.logging import logger
from app.services.admin_service import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


def check_admin_enabled():
    """Dependency to check if admin features are enabled."""
    if not settings.admin_enabled:
        raise HTTPException(
            status_code=503,
            detail="Admin features are not enabled",
        )


# =============================================================================
# Dashboard
# =============================================================================


@router.get(
    "/dashboard",
    summary="Get dashboard summary",
    description="Get aggregated statistics for the admin dashboard including user counts, application metrics, and system health.",
    dependencies=[Depends(check_admin_enabled)],
)
async def get_dashboard(
    admin: AdminUser = Depends(require_admin_role(AdminRole.VIEWER)),
):
    """
    Get dashboard summary with key metrics.

    Returns:
        Dashboard summary including user counts, application stats,
        queue depths, and health status.
    """
    logger.info(
        "Admin dashboard accessed",
        event_type="admin_dashboard_view",
        admin_id=admin.user_id,
    )

    return await admin_service.get_dashboard_summary()


# =============================================================================
# Analytics
# =============================================================================


@router.get(
    "/analytics/applications",
    summary="Get application analytics",
    description="Get time-series analytics for applications with customizable period and grouping.",
    dependencies=[Depends(check_admin_enabled)],
)
async def get_application_analytics(
    admin: AdminUser = Depends(require_admin_role(AdminRole.VIEWER)),
    period: Annotated[
        str,
        Query(description="Aggregation period: hour, day, week, month"),
    ] = "day",
    group_by: Annotated[
        str,
        Query(description="Group by field: status, portal, user"),
    ] = "status",
    from_date: Annotated[
        datetime | None,
        Query(alias="from", description="Start date (ISO 8601)"),
    ] = None,
    to_date: Annotated[
        datetime | None,
        Query(alias="to", description="End date (ISO 8601)"),
    ] = None,
):
    """
    Get application analytics with time-series data.

    Args:
        period: Aggregation period (hour, day, week, month)
        group_by: Field to group by (status, portal, user)
        from_date: Start date for the query range
        to_date: End date for the query range

    Returns:
        Time-series data, totals, and breakdown by the specified field.
    """
    if period not in ["hour", "day", "week", "month"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid period. Must be: hour, day, week, month",
        )

    if group_by not in ["status", "portal", "user"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid group_by. Must be: status, portal, user",
        )

    return await admin_service.get_application_analytics(
        period=period,
        group_by=group_by,
        from_date=from_date,
        to_date=to_date,
    )


@router.get(
    "/analytics/users",
    summary="Get user analytics",
    description="Get user activity analytics including top users and activity trends.",
    dependencies=[Depends(check_admin_enabled)],
)
async def get_user_analytics(
    admin: AdminUser = Depends(require_admin_role(AdminRole.VIEWER)),
    from_date: Annotated[
        datetime | None,
        Query(alias="from", description="Start date (ISO 8601)"),
    ] = None,
    to_date: Annotated[
        datetime | None,
        Query(alias="to", description="End date (ISO 8601)"),
    ] = None,
):
    """
    Get user-related analytics.

    Returns:
        Top users by application count and activity metrics.
    """
    return await admin_service.get_user_analytics(
        from_date=from_date,
        to_date=to_date,
    )


@router.get(
    "/analytics/errors",
    summary="Get error analytics",
    description="Get error breakdown and trends for failed applications.",
    dependencies=[Depends(check_admin_enabled)],
)
async def get_error_analytics(
    admin: AdminUser = Depends(require_admin_role(AdminRole.VIEWER)),
    from_date: Annotated[
        datetime | None,
        Query(alias="from", description="Start date (ISO 8601)"),
    ] = None,
    to_date: Annotated[
        datetime | None,
        Query(alias="to", description="End date (ISO 8601)"),
    ] = None,
):
    """
    Get error breakdown and trends.

    Returns:
        Error breakdown by type and hourly error rate trend.
    """
    return await admin_service.get_error_analytics(
        from_date=from_date,
        to_date=to_date,
    )


# =============================================================================
# User Management
# =============================================================================


@router.get(
    "/users",
    summary="List users",
    description="List all users with their application statistics.",
    dependencies=[Depends(check_admin_enabled)],
)
async def list_users(
    admin: AdminUser = Depends(require_admin_role(AdminRole.VIEWER)),
    search: Annotated[
        str | None,
        Query(description="Search by user ID"),
    ] = None,
    sort: Annotated[
        str,
        Query(description="Sort by: total_applications, last_active"),
    ] = "total_applications",
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Results per page"),
    ] = 20,
    offset: Annotated[
        int,
        Query(ge=0, description="Pagination offset"),
    ] = 0,
):
    """
    List users with their statistics.

    Args:
        search: Search term for user ID
        sort: Sort field
        limit: Number of results
        offset: Pagination offset

    Returns:
        List of users with statistics and pagination info.
    """
    return await admin_service.list_users(
        search=search,
        sort_by=sort,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/users/{user_id}",
    summary="Get user details",
    description="Get detailed information about a specific user.",
    dependencies=[Depends(check_admin_enabled)],
)
async def get_user_details(
    user_id: str,
    admin: AdminUser = Depends(require_admin_role(AdminRole.VIEWER)),
):
    """
    Get detailed information about a user.

    Args:
        user_id: User ID to look up

    Returns:
        User details including statistics and recent applications.
    """
    user = await admin_service.get_user_details(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post(
    "/users/{user_id}/actions",
    summary="Perform user action",
    description="Perform administrative actions on a user (requires OPERATOR role).",
    dependencies=[Depends(check_admin_enabled)],
)
async def user_action(
    user_id: str,
    action: Annotated[
        str,
        Query(description="Action: reset_rate_limit, block, unblock"),
    ],
    admin: AdminUser = Depends(require_admin_role(AdminRole.OPERATOR)),
):
    """
    Perform an administrative action on a user.

    Available actions:
    - reset_rate_limit: Reset the user's rate limit counter
    - block: Block user from submitting applications
    - unblock: Unblock a blocked user

    Args:
        user_id: Target user ID
        action: Action to perform

    Returns:
        Action result message.
    """
    valid_actions = ["reset_rate_limit", "block", "unblock"]
    if action not in valid_actions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action. Must be one of: {', '.join(valid_actions)}",
        )

    logger.info(
        f"Admin action: {action} on user {user_id}",
        event_type="admin_user_action",
        admin_id=admin.user_id,
        target_user_id=user_id,
        action=action,
    )

    # Placeholder - would integrate with rate limit and user management
    if action == "reset_rate_limit":
        return {"message": f"Rate limit reset for user {user_id}", "user_id": user_id}
    elif action == "block":
        return {"message": f"User {user_id} blocked", "user_id": user_id}
    elif action == "unblock":
        return {"message": f"User {user_id} unblocked", "user_id": user_id}


# =============================================================================
# Queue Management
# =============================================================================


@router.get(
    "/queues",
    summary="Get queue status",
    description="Get status of all message queues.",
    dependencies=[Depends(check_admin_enabled)],
)
async def get_queues(
    admin: AdminUser = Depends(require_admin_role(AdminRole.VIEWER)),
):
    """
    Get status of all message queues.

    Returns:
        Queue depths and health status.
    """
    # This would integrate with RabbitMQ Management API for full metrics
    from app.core.mongo import applications_collection

    pending = await applications_collection.count_documents({"status": "pending"})
    processing = await applications_collection.count_documents({"status": "processing"})

    return {
        "queues": [
            {
                "name": settings.application_processing_queue,
                "depth": pending + processing,
                "pending": pending,
                "processing": processing,
                "status": "healthy" if pending < 100 else "warning",
            },
            {
                "name": settings.application_dlq,
                "depth": 0,  # Would need RabbitMQ API
                "status": "healthy",
            },
        ],
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.post(
    "/queues/{queue_name}/actions",
    summary="Perform queue action",
    description="Perform administrative actions on a queue (requires OPERATOR role).",
    dependencies=[Depends(check_admin_enabled)],
)
async def queue_action(
    queue_name: str,
    action: Annotated[
        str,
        Query(description="Action: purge, pause, resume, reprocess_dlq"),
    ],
    admin: AdminUser = Depends(require_admin_role(AdminRole.OPERATOR)),
):
    """
    Perform an administrative action on a queue.

    Available actions:
    - purge: Clear all messages from the queue
    - pause: Pause queue consumption
    - resume: Resume queue consumption
    - reprocess_dlq: Move DLQ messages back to main queue

    Args:
        queue_name: Target queue name
        action: Action to perform

    Returns:
        Action result message.
    """
    valid_actions = ["purge", "pause", "resume", "reprocess_dlq"]
    if action not in valid_actions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action. Must be one of: {', '.join(valid_actions)}",
        )

    logger.warning(
        f"Admin queue action: {action} on {queue_name}",
        event_type="admin_queue_action",
        admin_id=admin.user_id,
        queue_name=queue_name,
        action=action,
    )

    # Placeholder - would integrate with RabbitMQ Management API
    return {
        "message": f"Action '{action}' queued for {queue_name}",
        "queue_name": queue_name,
        "action": action,
        "status": "pending",
    }


# =============================================================================
# Audit Log
# =============================================================================


@router.get(
    "/audit-log",
    summary="Get audit log",
    description="Get audit log entries for admin actions and system events.",
    dependencies=[Depends(check_admin_enabled)],
)
async def get_audit_log(
    admin: AdminUser = Depends(require_admin_role(AdminRole.VIEWER)),
    user_id: Annotated[
        str | None,
        Query(description="Filter by user ID"),
    ] = None,
    action: Annotated[
        str | None,
        Query(description="Filter by action type"),
    ] = None,
    from_date: Annotated[
        datetime | None,
        Query(alias="from", description="Start date"),
    ] = None,
    to_date: Annotated[
        datetime | None,
        Query(alias="to", description="End date"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Results per page"),
    ] = 50,
):
    """
    Get audit log entries.

    Args:
        user_id: Filter by user ID
        action: Filter by action type
        from_date: Start date
        to_date: End date
        limit: Maximum results

    Returns:
        List of audit log entries.
    """
    # Placeholder - would query from audit log collection
    # The audit module already logs events, but a dedicated collection
    # would provide queryable audit history

    return {
        "entries": [],
        "pagination": {
            "limit": limit,
            "total": 0,
            "has_more": False,
        },
        "filters": {
            "user_id": user_id,
            "action": action,
            "from": from_date.isoformat() + "Z" if from_date else None,
            "to": to_date.isoformat() + "Z" if to_date else None,
        },
    }


# =============================================================================
# System Info
# =============================================================================


@router.get(
    "/system",
    summary="Get system info",
    description="Get system information and configuration (requires ADMIN role).",
    dependencies=[Depends(check_admin_enabled)],
)
async def get_system_info(
    admin: AdminUser = Depends(require_admin_role(AdminRole.ADMIN)),
):
    """
    Get system configuration and info.

    Returns:
        System configuration (non-sensitive values only).
    """
    return {
        "service_name": settings.service_name,
        "environment": settings.environment,
        "debug": settings.debug,
        "features": {
            "async_processing": settings.async_processing_enabled,
            "rate_limiting": settings.rate_limit_enabled,
            "webhooks": settings.webhooks_enabled,
            "migrations": settings.migrations_enabled,
            "admin": settings.admin_enabled,
            "cache": settings.cache_enabled,
        },
        "api_versions": {
            "supported": settings.api_supported_versions,
            "default": settings.api_default_version,
            "deprecated": settings.api_deprecated_versions,
        },
        "limits": {
            "rate_limit_applications": settings.rate_limit_applications,
            "rate_limit_requests": settings.rate_limit_requests,
            "webhook_max_per_user": settings.webhook_max_per_user,
        },
    }
