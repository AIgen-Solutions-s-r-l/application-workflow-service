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
    mongo_server_selection_timeout_ms: int = int(os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "5000"))
    mongo_socket_timeout_ms: int = int(os.getenv("MONGO_SOCKET_TIMEOUT_MS", "30000"))

    # RabbitMQ settings
    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    middleware_queue: str = os.getenv("MIDDLEWARE_QUEUE", "middleware_notification_queue")
    application_processing_queue: str = os.getenv("APPLICATION_PROCESSING_QUEUE", "application_processing_queue")
    application_dlq: str = os.getenv("APPLICATION_DLQ", "application_dlq")

    # Async processing settings
    async_processing_enabled: bool = os.getenv("ASYNC_PROCESSING_ENABLED", "True").lower() == "true"

    # Rate limiting settings
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    rate_limit_enabled: bool = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"
    rate_limit_applications: str = os.getenv("RATE_LIMIT_APPLICATIONS", "100/hour")
    rate_limit_requests: str = os.getenv("RATE_LIMIT_REQUESTS", "1000/hour")

    # Retry settings
    max_retries: int = int(os.getenv("MAX_RETRIES", "5"))
    retry_base_delay: float = float(os.getenv("RETRY_BASE_DELAY", "1.0"))
    retry_max_delay: float = float(os.getenv("RETRY_MAX_DELAY", "16.0"))

    # Authentication settings
    secret_key: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    algorithm: str = os.getenv("ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

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
            base_config.update({
                "json_logs": False,
                "log_level": "DEBUG" if self.debug else "INFO"
            })

        return base_config

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()