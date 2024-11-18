import aio_pika
import asyncio
import json
import logging

class AsyncRabbitMQClient:
    def __init__(self, rabbitmq_url: str, queue: str):
        self.rabbitmq_url = rabbitmq_url
        self.queue = queue
        self.connection = None
        self.channel = None

    async def connect(self) -> None:
        """Establish an asynchronous connection to RabbitMQ using aio_pika."""
        self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
        self.channel = await self.connection.channel()
        await self.channel.declare_queue(self.queue, durable=True)
        logging.info("RabbitMQ connection and channel initialized.")

    async def send_message(self, queue: str, message: dict):
        """Asynchronously send a message to the specified queue."""
        if not self.channel:
            await self.connect()

        message_body = json.dumps(message).encode()
        await self.channel.default_exchange.publish(
            aio_pika.Message(body=message_body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=queue
        )
        logging.info(f"Message sent to queue '{queue}': {message}")

    async def get_message(self) -> str:
        """Retrieve a single message from the queue asynchronously."""
        if not self.channel:
            await self.connect()

        queue = await self.channel.declare_queue(self.queue, durable=True)
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    body = message.body.decode('utf-8')
                    logging.info(f"Message received from queue '{self.queue}': {body}")
                    return body

    async def close_connection(self):
        """Close the RabbitMQ connection."""
        if self.connection:
            await self.connection.close()
            logging.info("RabbitMQ connection closed.")