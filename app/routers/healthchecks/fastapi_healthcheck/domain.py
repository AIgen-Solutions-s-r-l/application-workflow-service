from abc import ABC, abstractmethod

from .enum import HealthCheckStatusEnum


class HealthCheckInterface(ABC):
    _connectionUri: str
    _alias: str
    _tags: list[str] | None

    @abstractmethod
    def setConnectionUri(self, value: str) -> None:
        """ConnectionUri will be the value that is requested to check the health of an endpoint."""
        pass

    @abstractmethod
    def setName(self, value: str) -> None:
        """The Name is the friendly name of the health object."""
        pass

    @abstractmethod
    def getService(self) -> str:
        """The Service is a definition of what kind of endpoint we are checking on."""
        pass

    @abstractmethod
    def getTags(self) -> list[str]:
        pass

    @abstractmethod
    async def __checkHealth__(self) -> HealthCheckStatusEnum:
        """Requests data from the endpoint to validate health."""
        pass
