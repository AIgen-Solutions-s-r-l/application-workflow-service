from datetime import datetime

from .domain import HealthCheckInterface
from .enum import HealthCheckStatusEnum
from .model import HealthCheckEntityModel, HealthCheckModel


class HealthCheckFactory:
    _healthItems: list[HealthCheckInterface]
    _health: HealthCheckModel

    def __init__(self) -> None:
        self._healthItems = []

    def add(self, item: HealthCheckInterface) -> None:
        self._healthItems.append(item)

    def __startTimer__(self, entityTimer: bool) -> None:
        if entityTimer:
            self._entityStartTime = datetime.now()
        else:
            self._totalStartTime = datetime.now()

    def __stopTimer__(self, entityTimer: bool) -> None:
        if entityTimer:
            self._entityStopTime = datetime.now()
        else:
            self._totalStopTime = datetime.now()

    def __getTimeTaken__(self, entityTimer: bool) -> datetime:
        if entityTimer:
            return self._entityStopTime - self._entityStartTime
        return self._totalStopTime - self._totalStartTime

    async def __dumpModel__(self, model: HealthCheckModel) -> str:
        """This goes and convert python objects to something a json object."""
        entities_list = []
        for i in model.entities:
            i.status = i.status.value
            i.timeTaken = str(i.timeTaken)
            entities_list.append(dict(i))

        model.entities = entities_list
        model.status = model.status.value
        model.totalTimeTaken = str(model.totalTimeTaken)

        return dict(model)

    async def check(self) -> HealthCheckModel:
        self._health = HealthCheckModel()
        self.__startTimer__(False)
        for i in self._healthItems:
            # Generate the model
            if not hasattr(i, "_tags"):
                i._tags = []
            item = HealthCheckEntityModel(alias=i._alias, tags=i._tags if i._tags else [])

            # Track how long the entity took to respond
            self.__startTimer__(True)
            item.status = await i.__checkHealth__()
            self.__stopTimer__(True)
            item.timeTaken = self.__getTimeTaken__(True)

            # if we have one dependency unhealthy, the service in unhealthy
            if item.status == HealthCheckStatusEnum.UNHEALTHY:
                self._health.status = HealthCheckStatusEnum.UNHEALTHY

            self._health.entities.append(item)
        self.__stopTimer__(False)
        self._health.totalTimeTaken = self.__getTimeTaken__(False)

        self._health = await self.__dumpModel__(self._health)

        return self._health


class HealthCheckBase:
    def setConnectionUri(self, value: str) -> None:
        if value == "":
            raise Exception(f"{self._service} ConnectionUri is missing a value.")
        self._connectionUri = value

    def getConnectionUri(self) -> str:
        return self._connectionUri

    def setName(self, value: str) -> str:
        if not value:
            raise Exception("Missing a valid name.")
        self._name = value

    def getService(self) -> str:
        return self._service

    def getTags(self) -> list[str]:
        return self._tags

    def getAlias(self) -> str:
        return self._alias
