import logging
from contextlib import asynccontextmanager
from threading import Thread
from fastapi import FastAPI
import asyncio  # Import asyncio for running async calls in threads

from core.config import Settings
from core.rabbitmq_client import RabbitMQClient
from core.mongo import get_resume_by_user_id, save_application_with_resume
from routers.example_router import router as example_router

logging.basicConfig(level=logging.DEBUG)

# Load settings
settings = Settings()

async def async_message_callback(user_id: str, lista_jobs_da_applicare: list):
    """Asynchronous helper function to fetch resume and save application data."""
    try:
        # Fetch resume and save the complete data structure in MongoDB
        resume = await get_resume_by_user_id(user_id)
        if resume:
            application_id = await save_application_with_resume(user_id, resume, lista_jobs_da_applicare)
            logging.info(f"Saved application with ID: {application_id}")
        else:
            logging.warning(f"No resume found for user_id: {user_id}")

    except Exception as e:
        logging.error(f"Error processing message: {e}")

def message_callback(ch, method, properties, body):
    """
    Synchronous callback function to process each message from RabbitMQ.
    Parameters:
    - ch: Channel - The RabbitMQ channel
    - method: - RabbitMQ method frame
    - properties: - RabbitMQ properties
    - body: bytes - The message content
    """
    logging.info(f"Received message: {body.decode()}")
    user_id = "sample_user_id"  # Replace with actual data parsing
    lista_jobs_da_applicare = [{"job_id": "job1"}, {"job_id": "job2"}]  # Replace with actual job list
    
    # Run the async callback in the event loop
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_message_callback(user_id, lista_jobs_da_applicare))

# RabbitMQ client setup
rabbit_client = RabbitMQClient(
    rabbitmq_url=settings.rabbitmq_url,
    queue="my_queue",
    callback=message_callback
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # RabbitMQ client I/O loop in a background thread
    rabbit_thread = Thread(target=rabbit_client.start)
    rabbit_thread.start()
    logging.info("RabbitMQ client started in background thread")

    yield

    # Stop RabbitMQ client and join thread
    rabbit_client.stop()
    rabbit_thread.join()
    logging.info("RabbitMQ client connection closed")

# Initialize FastAPI
app = FastAPI(lifespan=lifespan)

# Root endpoint for testing
@app.get("/")
async def root():
    return {"message": "Application Manager Service is running!"}

app.include_router(example_router)