"""
Webhook models for event notifications.

Provides models for:
- Webhook registration and configuration
- Webhook delivery tracking
- Event types and payloads
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class WebhookEventType(str, Enum):
    """Supported webhook event types."""

    APPLICATION_SUBMITTED = "application.submitted"
    APPLICATION_PROCESSING = "application.processing"
    APPLICATION_COMPLETED = "application.completed"
    APPLICATION_FAILED = "application.failed"
    BATCH_COMPLETED = "batch.completed"
    RATE_LIMIT_EXCEEDED = "rate_limit.exceeded"


class WebhookStatus(str, Enum):
    """Webhook status."""

    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"  # Auto-disabled due to failures


class DeliveryStatus(str, Enum):
    """Webhook delivery status."""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    PERMANENTLY_FAILED = "permanently_failed"


class Webhook(BaseModel):
    """Webhook registration model."""

    id: str = Field(..., description="Unique webhook ID")
    user_id: str = Field(..., description="Owner user ID")
    url: str = Field(..., description="Webhook endpoint URL (HTTPS)")
    secret: str = Field(..., description="HMAC secret for signature verification")
    name: str | None = Field(None, description="Optional friendly name")
    description: str | None = Field(None, description="Optional description")
    events: list[WebhookEventType] = Field(
        ..., description="List of events to subscribe to"
    )
    status: WebhookStatus = Field(
        default=WebhookStatus.ACTIVE, description="Webhook status"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    # Delivery statistics
    total_deliveries: int = Field(default=0, description="Total delivery attempts")
    successful_deliveries: int = Field(default=0, description="Successful deliveries")
    failed_deliveries: int = Field(default=0, description="Failed deliveries")
    consecutive_failures: int = Field(
        default=0, description="Consecutive failures (reset on success)"
    )
    last_delivery_at: datetime | None = Field(
        None, description="Last delivery attempt timestamp"
    )
    last_success_at: datetime | None = Field(
        None, description="Last successful delivery timestamp"
    )
    last_error: str | None = Field(None, description="Last error message")

    class Config:
        use_enum_values = True


class WebhookCreate(BaseModel):
    """Request model for creating a webhook."""

    url: HttpUrl = Field(..., description="Webhook endpoint URL (must be HTTPS)")
    name: str | None = Field(None, max_length=100, description="Optional friendly name")
    description: str | None = Field(
        None, max_length=500, description="Optional description"
    )
    events: list[WebhookEventType] = Field(
        ..., min_length=1, description="Events to subscribe to"
    )


class WebhookUpdate(BaseModel):
    """Request model for updating a webhook."""

    url: HttpUrl | None = Field(None, description="New webhook URL")
    name: str | None = Field(None, max_length=100, description="New name")
    description: str | None = Field(None, max_length=500, description="New description")
    events: list[WebhookEventType] | None = Field(
        None, min_length=1, description="New event subscriptions"
    )
    status: WebhookStatus | None = Field(None, description="New status")


class WebhookResponse(BaseModel):
    """Response model for webhook operations."""

    id: str
    user_id: str
    url: str
    name: str | None
    description: str | None
    events: list[WebhookEventType]
    status: WebhookStatus
    created_at: datetime
    updated_at: datetime
    total_deliveries: int
    successful_deliveries: int
    failed_deliveries: int
    last_delivery_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None

    class Config:
        use_enum_values = True


class WebhookWithSecret(WebhookResponse):
    """Response model including secret (only for creation)."""

    secret: str = Field(..., description="HMAC secret - store securely, shown only once")


class WebhookDelivery(BaseModel):
    """Webhook delivery record."""

    id: str = Field(..., description="Unique delivery ID")
    webhook_id: str = Field(..., description="Associated webhook ID")
    user_id: str = Field(..., description="User ID for filtering")
    event_type: WebhookEventType = Field(..., description="Event type")
    payload: dict[str, Any] = Field(..., description="Event payload")
    status: DeliveryStatus = Field(
        default=DeliveryStatus.PENDING, description="Delivery status"
    )
    attempts: int = Field(default=0, description="Delivery attempts")
    max_attempts: int = Field(default=5, description="Maximum retry attempts")
    created_at: datetime = Field(..., description="Creation timestamp")
    next_retry_at: datetime | None = Field(None, description="Next retry timestamp")
    delivered_at: datetime | None = Field(None, description="Successful delivery time")
    response_status: int | None = Field(None, description="HTTP response status code")
    response_body: str | None = Field(
        None, description="Response body (truncated to 1000 chars)"
    )
    error: str | None = Field(None, description="Error message if failed")
    duration_ms: int | None = Field(None, description="Request duration in ms")

    class Config:
        use_enum_values = True


class WebhookDeliveryResponse(BaseModel):
    """Response model for delivery listing."""

    id: str
    webhook_id: str
    event_type: WebhookEventType
    status: DeliveryStatus
    attempts: int
    created_at: datetime
    delivered_at: datetime | None
    response_status: int | None
    error: str | None
    duration_ms: int | None

    class Config:
        use_enum_values = True


class WebhookPayload(BaseModel):
    """Standard webhook payload structure."""

    id: str = Field(..., description="Delivery ID")
    event: WebhookEventType = Field(..., description="Event type")
    created_at: str = Field(..., description="Event timestamp (ISO 8601)")
    data: dict[str, Any] = Field(..., description="Event-specific data")


class WebhookTestResponse(BaseModel):
    """Response from webhook test endpoint."""

    success: bool
    delivery_id: str
    response_status: int | None
    response_time_ms: int | None
    error: str | None
