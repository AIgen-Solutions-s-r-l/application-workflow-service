"""
Audit logging for security-sensitive operations.

Provides structured logging for:
- Authentication events (login, logout, token refresh)
- Authorization events (access granted/denied)
- Data access events (read, write, delete)
- Administrative actions
"""
import json
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from dataclasses import dataclass, asdict

from app.core.correlation import get_correlation_id
from app.log.logging import logger


class AuditEventType(str, Enum):
    """Types of audit events."""
    # Authentication events
    AUTH_LOGIN_SUCCESS = "auth.login.success"
    AUTH_LOGIN_FAILURE = "auth.login.failure"
    AUTH_LOGOUT = "auth.logout"
    AUTH_TOKEN_REFRESH = "auth.token.refresh"
    AUTH_TOKEN_INVALID = "auth.token.invalid"
    AUTH_TOKEN_EXPIRED = "auth.token.expired"

    # Authorization events
    AUTHZ_ACCESS_GRANTED = "authz.access.granted"
    AUTHZ_ACCESS_DENIED = "authz.access.denied"
    AUTHZ_PERMISSION_CHECK = "authz.permission.check"

    # Application events
    APP_CREATED = "application.created"
    APP_UPDATED = "application.updated"
    APP_DELETED = "application.deleted"
    APP_STATUS_CHANGED = "application.status.changed"
    APP_ACCESSED = "application.accessed"

    # Resume events
    RESUME_UPLOADED = "resume.uploaded"
    RESUME_ACCESSED = "resume.accessed"
    RESUME_DELETED = "resume.deleted"

    # Administrative events
    ADMIN_CONFIG_CHANGED = "admin.config.changed"
    ADMIN_USER_ACTION = "admin.user.action"

    # Security events
    SECURITY_RATE_LIMIT_EXCEEDED = "security.rate_limit.exceeded"
    SECURITY_SUSPICIOUS_ACTIVITY = "security.suspicious.activity"
    SECURITY_INPUT_VALIDATION_FAILED = "security.input.validation_failed"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Structured audit event."""
    event_type: AuditEventType
    timestamp: str
    correlation_id: Optional[str]
    user_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[str]
    action: str
    outcome: str  # "success" or "failure"
    severity: AuditSeverity
    details: Optional[dict]
    error_message: Optional[str]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["severity"] = self.severity.value
        return data

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class AuditLogger:
    """
    Audit logger for security-sensitive operations.

    Usage:
        audit = AuditLogger()
        audit.log_auth_success(user_id="123", ip_address="192.168.1.1")
        audit.log_data_access(user_id="123", resource_type="application", resource_id="456")
    """

    def __init__(self):
        """Initialize the audit logger."""
        self._logger = logger.bind(audit=True)

    def _log(self, event: AuditEvent) -> None:
        """Log an audit event."""
        log_method = {
            AuditSeverity.INFO: self._logger.info,
            AuditSeverity.WARNING: self._logger.warning,
            AuditSeverity.ERROR: self._logger.error,
            AuditSeverity.CRITICAL: self._logger.critical
        }.get(event.severity, self._logger.info)

        log_method(
            f"AUDIT: {event.event_type.value} - {event.action}",
            extra={"audit_event": event.to_dict()}
        )

    def _create_event(
        self,
        event_type: AuditEventType,
        action: str,
        outcome: str = "success",
        severity: AuditSeverity = AuditSeverity.INFO,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
        error_message: Optional[str] = None
    ) -> AuditEvent:
        """Create an audit event."""
        return AuditEvent(
            event_type=event_type,
            timestamp=datetime.utcnow().isoformat() + "Z",
            correlation_id=get_correlation_id(),
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            outcome=outcome,
            severity=severity,
            details=details,
            error_message=error_message
        )

    # Authentication events
    def log_auth_success(
        self,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """Log successful authentication."""
        event = self._create_event(
            event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
            action="User authenticated successfully",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        self._log(event)

    def log_auth_failure(
        self,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        reason: Optional[str] = None
    ) -> None:
        """Log failed authentication attempt."""
        event = self._create_event(
            event_type=AuditEventType.AUTH_LOGIN_FAILURE,
            action="Authentication failed",
            outcome="failure",
            severity=AuditSeverity.WARNING,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            error_message=reason
        )
        self._log(event)

    def log_token_invalid(
        self,
        ip_address: Optional[str] = None,
        reason: Optional[str] = None
    ) -> None:
        """Log invalid token usage."""
        event = self._create_event(
            event_type=AuditEventType.AUTH_TOKEN_INVALID,
            action="Invalid token presented",
            outcome="failure",
            severity=AuditSeverity.WARNING,
            ip_address=ip_address,
            error_message=reason
        )
        self._log(event)

    # Authorization events
    def log_access_denied(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """Log access denied event."""
        event = self._create_event(
            event_type=AuditEventType.AUTHZ_ACCESS_DENIED,
            action=f"Access denied to {resource_type}",
            outcome="failure",
            severity=AuditSeverity.WARNING,
            user_id=user_id,
            ip_address=ip_address,
            resource_type=resource_type,
            resource_id=resource_id,
            error_message=reason
        )
        self._log(event)

    # Application events
    def log_application_created(
        self,
        user_id: str,
        application_id: str,
        job_count: int,
        ip_address: Optional[str] = None
    ) -> None:
        """Log application creation."""
        event = self._create_event(
            event_type=AuditEventType.APP_CREATED,
            action="Application created",
            user_id=user_id,
            ip_address=ip_address,
            resource_type="application",
            resource_id=application_id,
            details={"job_count": job_count}
        )
        self._log(event)

    def log_application_status_changed(
        self,
        user_id: str,
        application_id: str,
        old_status: str,
        new_status: str
    ) -> None:
        """Log application status change."""
        event = self._create_event(
            event_type=AuditEventType.APP_STATUS_CHANGED,
            action=f"Application status changed: {old_status} -> {new_status}",
            user_id=user_id,
            resource_type="application",
            resource_id=application_id,
            details={"old_status": old_status, "new_status": new_status}
        )
        self._log(event)

    def log_application_accessed(
        self,
        user_id: str,
        application_id: str,
        ip_address: Optional[str] = None
    ) -> None:
        """Log application data access."""
        event = self._create_event(
            event_type=AuditEventType.APP_ACCESSED,
            action="Application data accessed",
            user_id=user_id,
            ip_address=ip_address,
            resource_type="application",
            resource_id=application_id
        )
        self._log(event)

    # Resume events
    def log_resume_uploaded(
        self,
        user_id: str,
        resume_id: str,
        ip_address: Optional[str] = None
    ) -> None:
        """Log resume upload."""
        event = self._create_event(
            event_type=AuditEventType.RESUME_UPLOADED,
            action="Resume uploaded",
            user_id=user_id,
            ip_address=ip_address,
            resource_type="resume",
            resource_id=resume_id
        )
        self._log(event)

    # Security events
    def log_rate_limit_exceeded(
        self,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        endpoint: Optional[str] = None
    ) -> None:
        """Log rate limit exceeded."""
        event = self._create_event(
            event_type=AuditEventType.SECURITY_RATE_LIMIT_EXCEEDED,
            action="Rate limit exceeded",
            outcome="failure",
            severity=AuditSeverity.WARNING,
            user_id=user_id,
            ip_address=ip_address,
            details={"endpoint": endpoint}
        )
        self._log(event)

    def log_input_validation_failed(
        self,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        field: Optional[str] = None,
        reason: Optional[str] = None
    ) -> None:
        """Log input validation failure."""
        event = self._create_event(
            event_type=AuditEventType.SECURITY_INPUT_VALIDATION_FAILED,
            action="Input validation failed",
            outcome="failure",
            severity=AuditSeverity.WARNING,
            user_id=user_id,
            ip_address=ip_address,
            details={"field": field},
            error_message=reason
        )
        self._log(event)

    def log_suspicious_activity(
        self,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        description: str = "",
        details: Optional[dict] = None
    ) -> None:
        """Log suspicious activity."""
        event = self._create_event(
            event_type=AuditEventType.SECURITY_SUSPICIOUS_ACTIVITY,
            action=f"Suspicious activity detected: {description}",
            outcome="failure",
            severity=AuditSeverity.ERROR,
            user_id=user_id,
            ip_address=ip_address,
            details=details
        )
        self._log(event)


# Global audit logger instance
audit_logger = AuditLogger()
