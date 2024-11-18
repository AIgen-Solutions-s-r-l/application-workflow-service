# app/core/init_db.py

import asyncio
import logging

from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database import Base, database_url

# Set up logger
logger = logging.getLogger(__name__)


async def init_database() -> None:
    """
    Initialize the database and create all tables asynchronously.
    This should be run when setting up the application for the first time
    or when you need to reset the database.
    """
    try:
        # Create async engine
        engine = create_async_engine(database_url, echo=True)

        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialized successfully.")

    except Exception as e:
        logger.error(f"An error occurred while initializing the database: {str(e)}")
        raise
    finally:
        await engine.dispose()


async def verify_database() -> None:
    """
    Verify database connection and basic functionality.
    """
    engine = create_async_engine(database_url, echo=True)
    try:
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
            logger.info("Database connection verified successfully.")
    except Exception as e:
        logger.error(f"Database connection test failed: {str(e)}")
        raise
    finally:
        await engine.dispose()


if __name__ == '__main__':
    # Execute when you need without calling the app module
    async def main():
        await init_database()
        await verify_database()


    asyncio.run(main())
