import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    service_name: str = "app_manager"
    mongodb: str = os.getenv("MONGODB", "mongodb://localhost:27017")

    model_config = SettingsConfigDict(env_file=".env")
