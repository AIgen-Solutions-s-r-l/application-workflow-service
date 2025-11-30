import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuration class for environment variables and service settings.
    """

    # Service settings
    service_name: str = os.getenv("SERVICE_NAME", "app_manager")
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "True").lower() == "true"

    # Logging settings
    log_level: str = os.getenv("LOG_LEVEL", "DEBUG")
    syslog_host: str = os.getenv("SYSLOG_HOST", "172.17.0.1")
    syslog_port: int = int(os.getenv("SYSLOG_PORT", "5141"))
    json_logs: bool = os.getenv("JSON_LOGS", "True").lower() == "true"
    log_retention: str = os.getenv("LOG_RETENTION", "7 days")
    enable_logstash: bool = os.getenv("ENABLE_LOGSTASH", "True").lower() == "true"

    # MongoDB settings
    mongodb: str = os.getenv("MONGODB", "mongodb://localhost:27017")
    mongodb_database: str = os.getenv("MONGODB_DATABASE", "resumes")

    # MongoDB connection pool settings
    mongo_max_pool_size: int = int(os.getenv("MONGO_MAX_POOL_SIZE", "100"))
    mongo_min_pool_size: int = int(os.getenv("MONGO_MIN_POOL_SIZE", "10"))
    mongo_max_idle_time_ms: int = int(os.getenv("MONGO_MAX_IDLE_TIME_MS", "30000"))
    mongo_connect_timeout_ms: int = int(os.getenv("MONGO_CONNECT_TIMEOUT_MS", "5000"))
    mongo_server_selection_timeout_ms: int = int(
        os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "5000")
    )
    mongo_socket_timeout_ms: int = int(os.getenv("MONGO_SOCKET_TIMEOUT_MS", "30000"))

    # RabbitMQ settings
    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    middleware_queue: str = os.getenv("MIDDLEWARE_QUEUE", "middleware_notification_queue")
    application_processing_queue: str = os.getenv(
        "APPLICATION_PROCESSING_QUEUE", "application_processing_queue"
    )
    application_dlq: str = os.getenv("APPLICATION_DLQ", "application_dlq")

    # Async processing settings
    async_processing_enabled: bool = os.getenv("ASYNC_PROCESSING_ENABLED", "True").lower() == "true"

    # Redis settings
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_password: str | None = os.getenv("REDIS_PASSWORD", None)
    redis_ssl: bool = os.getenv("REDIS_SSL", "False").lower() == "true"

    # Cache settings
    cache_enabled: bool = os.getenv("CACHE_ENABLED", "True").lower() == "true"
    cache_default_ttl: int = int(os.getenv("CACHE_DEFAULT_TTL", "300"))
    cache_key_prefix: str = os.getenv("CACHE_KEY_PREFIX", "app_manager")
    cache_fallback_to_memory: bool = os.getenv("CACHE_FALLBACK_TO_MEMORY", "True").lower() == "true"

    # Rate limiting settings
    rate_limit_enabled: bool = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"
    rate_limit_applications: str = os.getenv("RATE_LIMIT_APPLICATIONS", "100/hour")
    rate_limit_requests: str = os.getenv("RATE_LIMIT_REQUESTS", "1000/hour")

    # Retry settings
    max_retries: int = int(os.getenv("MAX_RETRIES", "5"))
    retry_base_delay: float = float(os.getenv("RETRY_BASE_DELAY", "1.0"))
    retry_max_delay: float = float(os.getenv("RETRY_MAX_DELAY", "16.0"))

    # Migration settings
    migrations_enabled: bool = os.getenv("MIGRATIONS_ENABLED", "True").lower() == "true"
    migrations_auto_run: bool = os.getenv("MIGRATIONS_AUTO_RUN", "True").lower() == "true"
    migrations_lock_timeout: int = int(os.getenv("MIGRATIONS_LOCK_TIMEOUT", "300"))

    # API Versioning settings
    api_default_version: str = os.getenv("API_DEFAULT_VERSION", "v1")
    api_supported_versions: list[str] = os.getenv(
        "API_SUPPORTED_VERSIONS", "v1,v2"
    ).split(",")
    api_deprecated_versions: list[str] = os.getenv(
        "API_DEPRECATED_VERSIONS", ""
    ).split(",") if os.getenv("API_DEPRECATED_VERSIONS") else []
    api_deprecation_warnings: bool = os.getenv("API_DEPRECATION_WARNINGS", "True").lower() == "true"

    @property
    def api_sunset_dates(self) -> dict[str, str]:
        """
        Returns sunset dates for deprecated API versions.
        Format: API_SUNSET_DATES=v1:2025-12-31,v2:2026-06-30
        """
        dates_str = os.getenv("API_SUNSET_DATES", "")
        if not dates_str:
            return {}
        dates = {}
        for item in dates_str.split(","):
            if ":" in item:
                version, date = item.split(":", 1)
                dates[version.strip()] = date.strip()
        return dates

    # Authentication settings
    secret_key: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    algorithm: str = os.getenv("ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

    # Admin settings
    admin_enabled: bool = os.getenv("ADMIN_ENABLED", "True").lower() == "true"
    admin_role_claim: str = os.getenv("ADMIN_ROLE_CLAIM", "admin_role")
    admin_audit_retention_days: int = int(os.getenv("ADMIN_AUDIT_RETENTION_DAYS", "90"))
    admin_analytics_cache_ttl: int = int(os.getenv("ADMIN_ANALYTICS_CACHE_TTL", "300"))

    # Scheduler settings
    scheduler_enabled: bool = os.getenv("SCHEDULER_ENABLED", "True").lower() == "true"
    scheduler_timezone: str = os.getenv("SCHEDULER_TIMEZONE", "UTC")
    cleanup_retention_days: int = int(os.getenv("CLEANUP_RETENTION_DAYS", "90"))
    dlq_alert_threshold: int = int(os.getenv("DLQ_ALERT_THRESHOLD", "10"))

    # Webhook settings
    webhooks_enabled: bool = os.getenv("WEBHOOKS_ENABLED", "True").lower() == "true"
    webhook_timeout_seconds: int = int(os.getenv("WEBHOOK_TIMEOUT_SECONDS", "30"))
    webhook_max_retries: int = int(os.getenv("WEBHOOK_MAX_RETRIES", "5"))
    webhook_auto_disable_threshold: int = int(
        os.getenv("WEBHOOK_AUTO_DISABLE_THRESHOLD", "10")
    )
    webhook_require_https: bool = os.getenv("WEBHOOK_REQUIRE_HTTPS", "True").lower() == "true"
    webhook_max_per_user: int = int(os.getenv("WEBHOOK_MAX_PER_USER", "10"))

    # Environment-specific logging configuration
    @property
    def logging_config(self) -> dict:
        """
        Returns logging configuration based on environment.
        """
        base_config = {
            "app_name": self.service_name,
            "log_level": self.log_level,
            "syslog_host": self.syslog_host if self.enable_logstash else None,
            "syslog_port": self.syslog_port if self.enable_logstash else None,
            "json_logs": self.json_logs,
            "enable_logstash": self.enable_logstash,
        }

        if self.environment == "development":
            base_config.update({"json_logs": False, "log_level": "DEBUG" if self.debug else "INFO"})

        return base_config

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
