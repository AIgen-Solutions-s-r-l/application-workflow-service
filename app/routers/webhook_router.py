"""
Webhook management API router.

Provides endpoints for:
- Creating, listing, updating, deleting webhooks
- Viewing delivery history
- Testing webhooks
- Rotating secrets
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import get_current_user
from app.core.config import settings
from app.models.webhook import (
    WebhookCreate,
    WebhookDeliveryResponse,
    WebhookResponse,
    WebhookTestResponse,
    WebhookUpdate,
    WebhookWithSecret,
)
from app.services.webhook_service import webhook_service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def check_webhooks_enabled():
    """Dependency to check if webhooks feature is enabled."""
    if not settings.webhooks_enabled:
        raise HTTPException(
            status_code=503,
            detail="Webhooks feature is not enabled",
        )


@router.post(
    "",
    summary="Create a webhook",
    description=(
        "Register a new webhook endpoint to receive event notifications. "
        "The secret is returned only once - store it securely for signature verification."
    ),
    response_model=WebhookWithSecret,
    dependencies=[Depends(check_webhooks_enabled)],
)
async def create_webhook(
    webhook: WebhookCreate,
    current_user=Depends(get_current_user),
):
    """
    Create a new webhook registration.

    Args:
        webhook: Webhook configuration with URL and event subscriptions.
        current_user: Authenticated user ID.

    Returns:
        Created webhook including the secret (shown only once).
    """
    try:
        created = await webhook_service.create_webhook(current_user, webhook)
        return WebhookWithSecret(
            id=created.id,
            user_id=created.user_id,
            url=created.url,
            name=created.name,
            description=created.description,
            events=created.events,
            status=created.status,
            created_at=created.created_at,
            updated_at=created.updated_at,
            total_deliveries=created.total_deliveries,
            successful_deliveries=created.successful_deliveries,
            failed_deliveries=created.failed_deliveries,
            last_delivery_at=created.last_delivery_at,
            last_success_at=created.last_success_at,
            last_error=created.last_error,
            secret=created.secret,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "",
    summary="List webhooks",
    description="List all webhooks for the authenticated user.",
    response_model=list[WebhookResponse],
    dependencies=[Depends(check_webhooks_enabled)],
)
async def list_webhooks(
    current_user=Depends(get_current_user),
    include_disabled: bool = Query(
        default=False, description="Include disabled webhooks"
    ),
):
    """
    List all webhooks for the current user.

    Args:
        current_user: Authenticated user ID.
        include_disabled: Whether to include auto-disabled webhooks.

    Returns:
        List of webhooks (without secrets).
    """
    webhooks = await webhook_service.list_webhooks(current_user, include_disabled)
    return [
        WebhookResponse(
            id=w.id,
            user_id=w.user_id,
            url=w.url,
            name=w.name,
            description=w.description,
            events=w.events,
            status=w.status,
            created_at=w.created_at,
            updated_at=w.updated_at,
            total_deliveries=w.total_deliveries,
            successful_deliveries=w.successful_deliveries,
            failed_deliveries=w.failed_deliveries,
            last_delivery_at=w.last_delivery_at,
            last_success_at=w.last_success_at,
            last_error=w.last_error,
        )
        for w in webhooks
    ]


@router.get(
    "/{webhook_id}",
    summary="Get webhook details",
    description="Get details of a specific webhook including delivery statistics.",
    response_model=WebhookResponse,
    dependencies=[Depends(check_webhooks_enabled)],
)
async def get_webhook(
    webhook_id: str,
    current_user=Depends(get_current_user),
):
    """
    Get details of a specific webhook.

    Args:
        webhook_id: Webhook ID.
        current_user: Authenticated user ID.

    Returns:
        Webhook details (without secret).
    """
    webhook = await webhook_service.get_webhook(webhook_id, current_user)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return WebhookResponse(
        id=webhook.id,
        user_id=webhook.user_id,
        url=webhook.url,
        name=webhook.name,
        description=webhook.description,
        events=webhook.events,
        status=webhook.status,
        created_at=webhook.created_at,
        updated_at=webhook.updated_at,
        total_deliveries=webhook.total_deliveries,
        successful_deliveries=webhook.successful_deliveries,
        failed_deliveries=webhook.failed_deliveries,
        last_delivery_at=webhook.last_delivery_at,
        last_success_at=webhook.last_success_at,
        last_error=webhook.last_error,
    )


@router.patch(
    "/{webhook_id}",
    summary="Update webhook",
    description="Update webhook URL, events, or status.",
    response_model=WebhookResponse,
    dependencies=[Depends(check_webhooks_enabled)],
)
async def update_webhook(
    webhook_id: str,
    updates: WebhookUpdate,
    current_user=Depends(get_current_user),
):
    """
    Update a webhook.

    Args:
        webhook_id: Webhook ID.
        updates: Fields to update.
        current_user: Authenticated user ID.

    Returns:
        Updated webhook details.
    """
    try:
        webhook = await webhook_service.update_webhook(webhook_id, current_user, updates)
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")

        return WebhookResponse(
            id=webhook.id,
            user_id=webhook.user_id,
            url=webhook.url,
            name=webhook.name,
            description=webhook.description,
            events=webhook.events,
            status=webhook.status,
            created_at=webhook.created_at,
            updated_at=webhook.updated_at,
            total_deliveries=webhook.total_deliveries,
            successful_deliveries=webhook.successful_deliveries,
            failed_deliveries=webhook.failed_deliveries,
            last_delivery_at=webhook.last_delivery_at,
            last_success_at=webhook.last_success_at,
            last_error=webhook.last_error,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/{webhook_id}",
    summary="Delete webhook",
    description="Delete a webhook and its delivery history.",
    dependencies=[Depends(check_webhooks_enabled)],
)
async def delete_webhook(
    webhook_id: str,
    current_user=Depends(get_current_user),
):
    """
    Delete a webhook.

    Args:
        webhook_id: Webhook ID.
        current_user: Authenticated user ID.

    Returns:
        Success message.
    """
    deleted = await webhook_service.delete_webhook(webhook_id, current_user)
    if not deleted:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return {"message": "Webhook deleted", "webhook_id": webhook_id}


@router.post(
    "/{webhook_id}/rotate-secret",
    summary="Rotate webhook secret",
    description="Generate a new secret for signature verification. Old secret becomes invalid immediately.",
    dependencies=[Depends(check_webhooks_enabled)],
)
async def rotate_secret(
    webhook_id: str,
    current_user=Depends(get_current_user),
):
    """
    Rotate the webhook secret.

    Args:
        webhook_id: Webhook ID.
        current_user: Authenticated user ID.

    Returns:
        New secret (shown only once).
    """
    new_secret = await webhook_service.rotate_secret(webhook_id, current_user)
    if not new_secret:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return {
        "message": "Secret rotated successfully",
        "webhook_id": webhook_id,
        "secret": new_secret,
    }


@router.get(
    "/{webhook_id}/deliveries",
    summary="List deliveries",
    description="List recent delivery attempts for a webhook (for debugging).",
    response_model=list[WebhookDeliveryResponse],
    dependencies=[Depends(check_webhooks_enabled)],
)
async def list_deliveries(
    webhook_id: str,
    current_user=Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum results"),
):
    """
    List recent deliveries for a webhook.

    Args:
        webhook_id: Webhook ID.
        current_user: Authenticated user ID.
        limit: Maximum number of deliveries to return.

    Returns:
        List of delivery records.
    """
    # Verify webhook exists and belongs to user
    webhook = await webhook_service.get_webhook(webhook_id, current_user)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    deliveries = await webhook_service.list_deliveries(webhook_id, current_user, limit)

    return [
        WebhookDeliveryResponse(
            id=d.id,
            webhook_id=d.webhook_id,
            event_type=d.event_type,
            status=d.status,
            attempts=d.attempts,
            created_at=d.created_at,
            delivered_at=d.delivered_at,
            response_status=d.response_status,
            error=d.error,
            duration_ms=d.duration_ms,
        )
        for d in deliveries
    ]


@router.post(
    "/{webhook_id}/test",
    summary="Test webhook",
    description="Send a test event to verify the webhook endpoint is working correctly.",
    response_model=WebhookTestResponse,
    dependencies=[Depends(check_webhooks_enabled)],
)
async def test_webhook(
    webhook_id: str,
    current_user=Depends(get_current_user),
):
    """
    Send a test event to a webhook.

    Args:
        webhook_id: Webhook ID.
        current_user: Authenticated user ID.

    Returns:
        Test result with delivery details.
    """
    success, delivery_id, status_code, duration_ms, error = await webhook_service.test_webhook(
        webhook_id, current_user
    )

    if not delivery_id:
        raise HTTPException(status_code=404, detail=error or "Webhook not found")

    return WebhookTestResponse(
        success=success,
        delivery_id=delivery_id,
        response_status=status_code,
        response_time_ms=duration_ms,
        error=error,
    )
