from datetime import datetime

from pydantic import BaseModel

from .enum import HealthCheckStatusEnum


class HealthCheckEntityModel(BaseModel):
    alias: str
    status: HealthCheckStatusEnum | str = HealthCheckStatusEnum.HEALTHY
    timeTaken: datetime | None | str = ""
    tags: list[str] = []


class HealthCheckModel(BaseModel):
    status: HealthCheckStatusEnum | str = HealthCheckStatusEnum.HEALTHY
    totalTimeTaken: datetime | None | str = ""
    entities: list[HealthCheckEntityModel] = []
