import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    service_name: str = "coreService"

    class Config:
        env_file = ".env"
