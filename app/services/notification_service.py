from typing import Any, Dict
from app.log.logging import logger
from app.services.base_publisher import BasePublisher
from app.core.config import Settings

settings = Settings()

class NotificationPublisher(BasePublisher):
    def get_queue_name(self) -> str:
        return settings.middleware_queue
    
    async def publish_application_updated(self) -> None:
        """
        Publishes the notification about the update on the queue
        """
        logger.info("Publishing notification about application update", event_type="notification_publishing")

        await self.publish({"updated": True}, False)