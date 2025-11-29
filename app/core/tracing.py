"""
OpenTelemetry distributed tracing configuration.

Provides:
- Automatic instrumentation for FastAPI, MongoDB, and aio-pika
- Custom span creation for business operations
- Trace context propagation
- Export to various backends (Jaeger, OTLP, etc.)
"""
import os
from typing import Optional
from contextlib import contextmanager

from app.core.config import settings
from app.log.logging import logger

# Check if OpenTelemetry is available
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
    from opentelemetry.trace import Status, StatusCode, Span
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    from opentelemetry.propagate import set_global_textmap

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    logger.warning("OpenTelemetry not installed. Tracing disabled.")

# Try to import exporters
JAEGER_AVAILABLE = False
OTLP_AVAILABLE = False

if OTEL_AVAILABLE:
    try:
        from opentelemetry.exporter.jaeger.thrift import JaegerExporter
        JAEGER_AVAILABLE = True
    except ImportError:
        pass

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        OTLP_AVAILABLE = True
    except ImportError:
        pass


class TracingConfig:
    """Configuration for distributed tracing."""

    def __init__(self):
        self.enabled = os.getenv("TRACING_ENABLED", "false").lower() == "true"
        self.service_name = settings.service_name
        self.service_version = "1.0.0"

        # Exporter configuration
        self.exporter_type = os.getenv("TRACING_EXPORTER", "console")  # console, jaeger, otlp
        self.jaeger_host = os.getenv("JAEGER_HOST", "localhost")
        self.jaeger_port = int(os.getenv("JAEGER_PORT", "6831"))
        self.otlp_endpoint = os.getenv("OTLP_ENDPOINT", "http://localhost:4317")

        # Sampling configuration
        self.sample_rate = float(os.getenv("TRACING_SAMPLE_RATE", "1.0"))


tracing_config = TracingConfig()

# Global tracer
_tracer: Optional["trace.Tracer"] = None


def init_tracing() -> Optional["trace.Tracer"]:
    """
    Initialize OpenTelemetry tracing.

    Returns:
        Configured tracer or None if tracing is disabled.
    """
    global _tracer

    if not OTEL_AVAILABLE:
        logger.info("OpenTelemetry not available, tracing disabled")
        return None

    if not tracing_config.enabled:
        logger.info("Tracing is disabled via configuration")
        return None

    # Create resource with service information
    resource = Resource.create({
        SERVICE_NAME: tracing_config.service_name,
        SERVICE_VERSION: tracing_config.service_version,
        "deployment.environment": settings.environment
    })

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Configure exporter based on settings
    exporter = None

    if tracing_config.exporter_type == "jaeger" and JAEGER_AVAILABLE:
        exporter = JaegerExporter(
            agent_host_name=tracing_config.jaeger_host,
            agent_port=tracing_config.jaeger_port
        )
        logger.info(f"Jaeger exporter configured: {tracing_config.jaeger_host}:{tracing_config.jaeger_port}")

    elif tracing_config.exporter_type == "otlp" and OTLP_AVAILABLE:
        exporter = OTLPSpanExporter(
            endpoint=tracing_config.otlp_endpoint
        )
        logger.info(f"OTLP exporter configured: {tracing_config.otlp_endpoint}")

    else:
        # Default to console exporter for development
        exporter = ConsoleSpanExporter()
        logger.info("Console exporter configured for tracing")

    # Add span processor
    provider.add_span_processor(BatchSpanProcessor(exporter))

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    # Set up context propagation
    set_global_textmap(TraceContextTextMapPropagator())

    # Get tracer
    _tracer = trace.get_tracer(
        tracing_config.service_name,
        tracing_config.service_version
    )

    logger.info("OpenTelemetry tracing initialized")
    return _tracer


def get_tracer() -> Optional["trace.Tracer"]:
    """Get the configured tracer."""
    return _tracer


@contextmanager
def create_span(
    name: str,
    attributes: Optional[dict] = None,
    kind: Optional["trace.SpanKind"] = None
):
    """
    Create a new span for tracing.

    Args:
        name: Span name.
        attributes: Optional span attributes.
        kind: Optional span kind.

    Yields:
        The created span, or a no-op context if tracing is disabled.
    """
    if not OTEL_AVAILABLE or _tracer is None:
        # Yield a dummy context
        yield None
        return

    span_kind = kind or trace.SpanKind.INTERNAL

    with _tracer.start_as_current_span(name, kind=span_kind) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield span


def add_span_attributes(attributes: dict) -> None:
    """
    Add attributes to the current span.

    Args:
        attributes: Dictionary of attributes to add.
    """
    if not OTEL_AVAILABLE:
        return

    span = trace.get_current_span()
    if span and span.is_recording():
        for key, value in attributes.items():
            span.set_attribute(key, value)


def record_exception(exception: Exception) -> None:
    """
    Record an exception in the current span.

    Args:
        exception: The exception to record.
    """
    if not OTEL_AVAILABLE:
        return

    span = trace.get_current_span()
    if span and span.is_recording():
        span.record_exception(exception)
        span.set_status(Status(StatusCode.ERROR, str(exception)))


def set_span_status(success: bool, message: Optional[str] = None) -> None:
    """
    Set the status of the current span.

    Args:
        success: Whether the operation succeeded.
        message: Optional status message.
    """
    if not OTEL_AVAILABLE:
        return

    span = trace.get_current_span()
    if span and span.is_recording():
        if success:
            span.set_status(Status(StatusCode.OK, message))
        else:
            span.set_status(Status(StatusCode.ERROR, message))


# Instrumentation helpers for FastAPI
def instrument_fastapi(app) -> None:
    """
    Instrument FastAPI application with OpenTelemetry.

    Args:
        app: FastAPI application instance.
    """
    if not OTEL_AVAILABLE or not tracing_config.enabled:
        return

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented for tracing")
    except ImportError:
        logger.warning("opentelemetry-instrumentation-fastapi not installed")


def instrument_mongodb() -> None:
    """Instrument MongoDB with OpenTelemetry."""
    if not OTEL_AVAILABLE or not tracing_config.enabled:
        return

    try:
        from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
        PymongoInstrumentor().instrument()
        logger.info("MongoDB instrumented for tracing")
    except ImportError:
        logger.warning("opentelemetry-instrumentation-pymongo not installed")


def instrument_aiopika() -> None:
    """Instrument aio-pika (RabbitMQ) with OpenTelemetry."""
    if not OTEL_AVAILABLE or not tracing_config.enabled:
        return

    try:
        from opentelemetry.instrumentation.aio_pika import AioPikaInstrumentor
        AioPikaInstrumentor().instrument()
        logger.info("aio-pika instrumented for tracing")
    except ImportError:
        logger.warning("opentelemetry-instrumentation-aio-pika not installed")


# Decorator for tracing functions
def traced(
    name: Optional[str] = None,
    attributes: Optional[dict] = None
):
    """
    Decorator to trace a function.

    Args:
        name: Optional span name (defaults to function name).
        attributes: Optional span attributes.

    Returns:
        Decorated function.
    """
    def decorator(func):
        import functools
        import asyncio

        span_name = name or func.__name__

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with create_span(span_name, attributes) as span:
                try:
                    result = await func(*args, **kwargs)
                    set_span_status(True)
                    return result
                except Exception as e:
                    record_exception(e)
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with create_span(span_name, attributes) as span:
                try:
                    result = func(*args, **kwargs)
                    set_span_status(True)
                    return result
                except Exception as e:
                    record_exception(e)
                    raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
