from typing import Any, Dict
import logging

from app.services.base_publisher import BasePublisher
from app.core.config import settings

logger = logging.getLogger(__name__)

class NotificationPublisher(BasePublisher):
    def get_queue_name(self) -> str:
        return settings.middleware_queue
    
    async def publish_application_updated(self) -> None:
        """
        Publishes the notification about the update on the queue
        """
        logger.debug(f"Publishing notification about application update")

        await self.publish({"updated": True}, False)