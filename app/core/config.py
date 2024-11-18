import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "app_manager"
    apply_to_job_queue: str = "apply_to_job_queue"
    job_to_apply_queue: str = "job_to_apply_queue"
    mongodb: str = os.getenv("MONGODB", "mongodb://localhost:27017")

    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    database_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://testuser:testpassword@localhost:5432/matching")
    test_database_url: str = os.getenv("TEST_DATABASE_URL",
                                       "postgresql+asyncpg://testuser:testpassword@localhost:5432/test_matching")

    model_config = SettingsConfigDict(env_file=".env")
