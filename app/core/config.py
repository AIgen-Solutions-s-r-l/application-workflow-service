import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "app_manager"
    mongodb: str = os.getenv("MONGODB", "mongodb://localhost:27017")

    model_config = SettingsConfigDict(env_file=".env")

    # Authentication settings
    secret_key: str = "your-secret-key-here"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30