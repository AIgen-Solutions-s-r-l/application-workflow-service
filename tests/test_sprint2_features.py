"""
Tests for Sprint 2 features:
- Story #12: Async submission with queue publishing
- Story #13: ApplicationWorker consumer
- Story #14: Per-user rate limiting
- Story #15: Retry mechanism with exponential backoff
"""
import pytest
import json
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId

from app.core.config import settings
from app.core.retry import (
    RetryableError,
    NonRetryableError,
    MaxRetriesExceededError,
    calculate_backoff_delay,
    retry_with_backoff,
    with_retry,
    RetryContext
)
from app.core.rate_limit import (
    InMemoryRateLimiter,
    RateLimitExceeded,
    get_rate_limiter,
    get_user_identifier
)
from app.models.application import ApplicationStatus


class TestRetryMechanism:
    """Tests for Story #15: Retry mechanism with exponential backoff."""

    def test_calculate_backoff_delay_first_attempt(self):
        """Verify first attempt has base delay."""
        delay = calculate_backoff_delay(1, base_delay=1.0, max_delay=16.0)
        assert delay == 1.0

    def test_calculate_backoff_delay_exponential(self):
        """Verify exponential backoff calculation."""
        assert calculate_backoff_delay(1, base_delay=1.0, max_delay=16.0) == 1.0
        assert calculate_backoff_delay(2, base_delay=1.0, max_delay=16.0) == 2.0
        assert calculate_backoff_delay(3, base_delay=1.0, max_delay=16.0) == 4.0
        assert calculate_backoff_delay(4, base_delay=1.0, max_delay=16.0) == 8.0
        assert calculate_backoff_delay(5, base_delay=1.0, max_delay=16.0) == 16.0

    def test_calculate_backoff_delay_max_capped(self):
        """Verify delay is capped at max_delay."""
        delay = calculate_backoff_delay(10, base_delay=1.0, max_delay=16.0)
        assert delay == 16.0

    def test_retryable_error_exception(self):
        """Verify RetryableError can be raised and caught."""
        with pytest.raises(RetryableError):
            raise RetryableError("Network timeout")

    def test_non_retryable_error_exception(self):
        """Verify NonRetryableError can be raised and caught."""
        with pytest.raises(NonRetryableError):
            raise NonRetryableError("Invalid data")

    def test_max_retries_exceeded_error(self):
        """Verify MaxRetriesExceededError contains correct info."""
        original_error = ValueError("test error")
        error = MaxRetriesExceededError(
            message="Max retries exceeded",
            last_error=original_error,
            attempts=5
        )
        assert error.last_error is original_error
        assert error.attempts == 5

    @pytest.mark.asyncio
    async def test_retry_with_backoff_success_first_try(self):
        """Verify successful function returns immediately."""
        call_count = 0

        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_with_backoff(success_func, max_retries=3)
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_with_backoff_retry_then_success(self):
        """Verify function is retried on retryable error."""
        call_count = 0

        async def fail_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableError("Temporary failure")
            return "success"

        with patch('app.core.retry.asyncio.sleep', new_callable=AsyncMock):
            result = await retry_with_backoff(fail_then_success, max_retries=5)

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_with_backoff_non_retryable_error(self):
        """Verify non-retryable errors are not retried."""
        call_count = 0

        async def non_retryable_func():
            nonlocal call_count
            call_count += 1
            raise NonRetryableError("Invalid data")

        with pytest.raises(NonRetryableError):
            await retry_with_backoff(non_retryable_func, max_retries=5)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_with_backoff_max_retries_exceeded(self):
        """Verify MaxRetriesExceededError after exhausting retries."""
        async def always_fail():
            raise RetryableError("Always fails")

        with patch('app.core.retry.asyncio.sleep', new_callable=AsyncMock):
            with pytest.raises(MaxRetriesExceededError) as exc_info:
                await retry_with_backoff(always_fail, max_retries=3)

        assert exc_info.value.attempts == 4  # Initial + 3 retries

    @pytest.mark.asyncio
    async def test_retry_with_backoff_on_retry_callback(self):
        """Verify on_retry callback is called on each retry."""
        retry_calls = []

        async def fail_func():
            raise RetryableError("fail")

        def on_retry(attempt, error):
            retry_calls.append((attempt, str(error)))

        with patch('app.core.retry.asyncio.sleep', new_callable=AsyncMock):
            with pytest.raises(MaxRetriesExceededError):
                await retry_with_backoff(
                    fail_func,
                    max_retries=2,
                    on_retry=on_retry
                )

        assert len(retry_calls) == 2
        assert retry_calls[0][0] == 1
        assert retry_calls[1][0] == 2


class TestRetryContext:
    """Tests for RetryContext context manager."""

    @pytest.mark.asyncio
    async def test_retry_context_tracks_timestamps(self):
        """Verify RetryContext tracks start and end times."""
        async with RetryContext("app_123") as ctx:
            assert ctx.started_at is not None
            ctx.attempt = 1

        assert ctx.completed_at is not None
        assert ctx.completed_at >= ctx.started_at

    @pytest.mark.asyncio
    async def test_retry_context_records_errors(self):
        """Verify RetryContext records errors."""
        async with RetryContext("app_123") as ctx:
            ctx.attempt = 1
            ctx.record_error(ValueError("test error"))

        assert len(ctx.errors) == 1
        assert ctx.errors[0]["attempt"] == 1
        assert ctx.errors[0]["error_type"] == "ValueError"

    def test_retry_context_can_retry(self):
        """Verify can_retry property."""
        ctx = RetryContext("app_123", max_retries=3)
        ctx.attempt = 1
        assert ctx.can_retry is True

        ctx.attempt = 3
        assert ctx.can_retry is False

    def test_retry_context_to_dict(self):
        """Verify to_dict serialization."""
        ctx = RetryContext("app_123", max_retries=3)
        ctx.attempt = 2

        data = ctx.to_dict()
        assert data["application_id"] == "app_123"
        assert data["attempt"] == 2
        assert data["max_retries"] == 3


class TestWithRetryDecorator:
    """Tests for @with_retry decorator."""

    @pytest.mark.asyncio
    async def test_with_retry_decorator_success(self):
        """Verify decorator works with successful function."""
        @with_retry(max_retries=3)
        async def success_func():
            return "decorated success"

        result = await success_func()
        assert result == "decorated success"

    @pytest.mark.asyncio
    async def test_with_retry_decorator_preserves_function_name(self):
        """Verify decorator preserves function metadata."""
        @with_retry()
        async def my_function():
            """My docstring."""
            pass

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."


class TestRateLimiter:
    """Tests for Story #14: Per-user rate limiting."""

    def test_rate_limiter_parse_limit_hour(self):
        """Verify limit string parsing for hours."""
        limiter = InMemoryRateLimiter()
        count, seconds = limiter._parse_limit("100/hour")
        assert count == 100
        assert seconds == 3600

    def test_rate_limiter_parse_limit_minute(self):
        """Verify limit string parsing for minutes."""
        limiter = InMemoryRateLimiter()
        count, seconds = limiter._parse_limit("10/minute")
        assert count == 10
        assert seconds == 60

    def test_rate_limiter_parse_limit_invalid(self):
        """Verify invalid limit string raises error."""
        limiter = InMemoryRateLimiter()
        with pytest.raises(ValueError):
            limiter._parse_limit("invalid")

    def test_rate_limiter_allows_within_limit(self):
        """Verify requests within limit are allowed."""
        limiter = InMemoryRateLimiter()

        for i in range(5):
            allowed, remaining, limit, reset_at = limiter.check_rate_limit(
                user_id="user_1",
                limit_str="10/minute"
            )
            assert allowed is True
            assert remaining == 10 - (i + 1)
            assert limit == 10

    def test_rate_limiter_blocks_over_limit(self):
        """Verify requests over limit are blocked."""
        limiter = InMemoryRateLimiter()

        # Use up the limit
        for _ in range(10):
            limiter.check_rate_limit(
                user_id="user_1",
                limit_str="10/minute"
            )

        # Next request should be blocked
        allowed, remaining, limit, reset_at = limiter.check_rate_limit(
            user_id="user_1",
            limit_str="10/minute"
        )
        assert allowed is False
        assert remaining == 0

    def test_rate_limiter_per_user_isolation(self):
        """Verify rate limits are per-user."""
        limiter = InMemoryRateLimiter()

        # User 1 uses up limit
        for _ in range(10):
            limiter.check_rate_limit(user_id="user_1", limit_str="10/minute")

        # User 2 should still be allowed
        allowed, _, _, _ = limiter.check_rate_limit(
            user_id="user_2",
            limit_str="10/minute"
        )
        assert allowed is True

    def test_rate_limiter_get_headers(self):
        """Verify rate limit headers are generated correctly."""
        limiter = InMemoryRateLimiter()
        reset_at = datetime.utcnow()

        headers = limiter.get_headers(
            remaining=5,
            limit=100,
            reset_at=reset_at
        )

        assert headers["X-RateLimit-Limit"] == "100"
        assert headers["X-RateLimit-Remaining"] == "5"
        assert "X-RateLimit-Reset" in headers

    def test_get_rate_limiter_returns_singleton(self):
        """Verify get_rate_limiter returns global instance."""
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        assert limiter1 is limiter2

    def test_rate_limit_exceeded_exception(self):
        """Verify RateLimitExceeded has correct attributes."""
        reset_at = datetime.utcnow()
        exc = RateLimitExceeded(
            limit=100,
            reset_at=reset_at,
            retry_after=60
        )

        assert exc.limit == 100
        assert exc.reset_at == reset_at
        assert exc.retry_after == 60
        assert exc.status_code == 429


class TestQueueService:
    """Tests for Story #12: Queue service for async processing."""

    @pytest.mark.asyncio
    async def test_publish_application_for_processing(self):
        """Verify application is published to processing queue."""
        from app.services.queue_service import ApplicationQueueService

        with patch('app.services.queue_service.AsyncRabbitMQClient') as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client

            service = ApplicationQueueService()
            service._client = mock_client

            result = await service.publish_application_for_processing(
                application_id="app_123",
                user_id="user_456",
                job_count=5,
                cv_id="cv_789",
                style="modern"
            )

            assert result is True
            mock_client.publish_message.assert_called_once()
            call_args = mock_client.publish_message.call_args
            assert call_args[1]["queue_name"] == settings.application_processing_queue
            assert call_args[1]["persistent"] is True

    @pytest.mark.asyncio
    async def test_publish_application_disabled(self):
        """Verify publish is skipped when async processing is disabled."""
        from app.services.queue_service import ApplicationQueueService

        with patch.object(settings, 'async_processing_enabled', False):
            service = ApplicationQueueService()

            result = await service.publish_application_for_processing(
                application_id="app_123",
                user_id="user_456",
                job_count=5
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_publish_to_dlq(self):
        """Verify failed message is published to DLQ."""
        from app.services.queue_service import ApplicationQueueService

        with patch('app.services.queue_service.AsyncRabbitMQClient') as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client

            service = ApplicationQueueService()
            service._client = mock_client

            result = await service.publish_to_dlq(
                application_id="app_123",
                error_message="Processing failed",
                original_message={"test": "data"}
            )

            assert result is True
            mock_client.publish_message.assert_called_once()
            call_args = mock_client.publish_message.call_args
            assert call_args[1]["queue_name"] == settings.application_dlq


class TestApplicationWorker:
    """Tests for Story #13: ApplicationWorker consumer."""

    @pytest.mark.asyncio
    async def test_worker_is_retryable_error(self):
        """Verify retryable error classification."""
        from app.workers.application_worker import ApplicationWorker

        worker = ApplicationWorker()

        assert worker._is_retryable_error(Exception("Connection timeout")) is True
        assert worker._is_retryable_error(Exception("Network error")) is True
        assert worker._is_retryable_error(Exception("503 Service Unavailable")) is True
        assert worker._is_retryable_error(Exception("Invalid data")) is False

    @pytest.mark.asyncio
    async def test_worker_process_application_updates_status(self):
        """Verify worker updates application status during processing."""
        from app.workers.application_worker import ApplicationWorker

        with patch('app.workers.application_worker.applications_collection') as mock_collection:
            mock_collection.find_one = AsyncMock(return_value={
                "_id": ObjectId(),
                "user_id": "user_123",
                "jobs": [{"title": "Test Job"}]
            })

            with patch.object(ApplicationWorker, '_uploader') as mock_uploader:
                mock_uploader.update_application_status = AsyncMock(return_value=True)

                worker = ApplicationWorker()
                worker._uploader = mock_uploader

                await worker.process_application(
                    application_id=str(ObjectId()),
                    user_id="user_123"
                )

                # Should be called twice: PROCESSING and SUCCESS
                assert mock_uploader.update_application_status.call_count == 2

    @pytest.mark.asyncio
    async def test_worker_handle_message_success(self):
        """Verify worker handles valid message correctly."""
        from app.workers.application_worker import ApplicationWorker

        worker = ApplicationWorker()

        mock_message = AsyncMock()
        mock_message.body = json.dumps({
            "application_id": str(ObjectId()),
            "user_id": "user_123",
            "job_count": 5
        }).encode()

        with patch.object(worker, 'process_application', new_callable=AsyncMock):
            with patch('app.workers.application_worker.retry_with_backoff', new_callable=AsyncMock):
                await worker.handle_message(mock_message)
                mock_message.ack.assert_called_once()

    @pytest.mark.asyncio
    async def test_worker_handle_message_invalid_json(self):
        """Verify worker rejects invalid JSON messages."""
        from app.workers.application_worker import ApplicationWorker

        worker = ApplicationWorker()

        mock_message = AsyncMock()
        mock_message.body = b"invalid json"

        await worker.handle_message(mock_message)
        mock_message.reject.assert_called_once_with(requeue=False)


class TestApplicationSubmission:
    """Tests for Story #12: Async submission."""

    @pytest.mark.asyncio
    async def test_insert_application_publishes_to_queue(self):
        """Verify application submission publishes to processing queue."""
        from app.services.application_uploader_service import ApplicationUploaderService

        with patch('app.services.application_uploader_service.applications_collection') as mock_collection:
            mock_result = MagicMock()
            mock_result.inserted_id = ObjectId()
            mock_collection.insert_one = AsyncMock(return_value=mock_result)

            with patch('app.services.application_uploader_service.notification_publisher') as mock_notifier:
                mock_notifier.publish_application_submitted = AsyncMock()

                with patch('app.services.application_uploader_service.application_queue_service') as mock_queue:
                    mock_queue.publish_application_for_processing = AsyncMock(return_value=True)

                    service = ApplicationUploaderService()
                    app_id = await service.insert_application_jobs(
                        user_id="test_user",
                        job_list_to_apply=[{"title": "Test Job"}]
                    )

                    assert app_id is not None
                    mock_queue.publish_application_for_processing.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_application_skips_queue_when_disabled(self):
        """Verify queue publishing is skipped when async processing is disabled."""
        from app.services.application_uploader_service import ApplicationUploaderService

        with patch.object(settings, 'async_processing_enabled', False):
            with patch('app.services.application_uploader_service.applications_collection') as mock_collection:
                mock_result = MagicMock()
                mock_result.inserted_id = ObjectId()
                mock_collection.insert_one = AsyncMock(return_value=mock_result)

                with patch('app.services.application_uploader_service.notification_publisher') as mock_notifier:
                    mock_notifier.publish_application_submitted = AsyncMock()

                    with patch('app.services.application_uploader_service.application_queue_service') as mock_queue:
                        mock_queue.publish_application_for_processing = AsyncMock()

                        service = ApplicationUploaderService()
                        await service.insert_application_jobs(
                            user_id="test_user",
                            job_list_to_apply=[{"title": "Test Job"}]
                        )

                        mock_queue.publish_application_for_processing.assert_not_called()


class TestConfigSettings:
    """Tests for Sprint 2 configuration settings."""

    def test_config_has_async_processing_settings(self):
        """Verify async processing settings exist."""
        assert hasattr(settings, 'async_processing_enabled')
        assert hasattr(settings, 'application_processing_queue')
        assert hasattr(settings, 'application_dlq')

    def test_config_has_rate_limit_settings(self):
        """Verify rate limit settings exist."""
        assert hasattr(settings, 'rate_limit_enabled')
        assert hasattr(settings, 'rate_limit_applications')
        assert hasattr(settings, 'rate_limit_requests')

    def test_config_has_retry_settings(self):
        """Verify retry settings exist."""
        assert hasattr(settings, 'max_retries')
        assert hasattr(settings, 'retry_base_delay')
        assert hasattr(settings, 'retry_max_delay')
        assert settings.max_retries == 5
        assert settings.retry_base_delay == 1.0
        assert settings.retry_max_delay == 16.0
