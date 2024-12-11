import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.database import get_db
from app.models.job import SuccApp, Job


async def fetch_all_succ_app():
    """
    Fetch and display all rows from the succ_app table.
    """
    # Get the database session from the async generator
    async for db in get_db():
        session: AsyncSession = db
        try:
            # Query to fetch all rows from succ_app
            stmt = select(SuccApp)
            result = await session.execute(stmt)
            succ_apps = result.scalars().all()

            if not succ_apps:
                print("No entries found in the succ_app table.")
                return

            # Print all succ_app details
            for entry in succ_apps:
                print(f"User ID: {entry.user_id}, Job ID: {entry.job_id}")
        except Exception as e:
            print(f"Failed to fetch entries from succ_app table: {e}")
        finally:
            await session.close()


async def fetch_all_jobs():
    """
    Fetch and display all jobs from the Jobs table.
    """
    # Get the database session from the async generator
    async for db in get_db():
        session: AsyncSession = db
        try:
            # Query to fetch all jobs
            stmt = select(Job)
            result = await session.execute(stmt)
            jobs = result.scalars().all()

            if not jobs:
                print("No jobs found in the Jobs table.")
                return

            # Print all job details
            for job in jobs:
                print(f"Job ID: {job.job_id}, Title: {job.title}, Remote: {job.is_remote}, Posted Date: {job.posted_date}")
        except Exception as e:
            print(f"Failed to fetch jobs: {e}")
        finally:
            await session.close()


async def insert_single_row_in_succ_app(user_id: int, job_id: int):
    """
    Insert a single row into the succ_app table.

    Args:
        user_id (int): The user ID to associate with the job.
        job_id (int): The job ID to associate with the user.
    """
    # Get the database session from the async generator
    async for db in get_db():  # Correctly handle the async generator
        session: AsyncSession = db

        try:
            # Create a new SuccApp instance
            succ_app_entry = SuccApp(user_id=user_id, job_id=job_id)

            # Add and commit the entry
            session.add(succ_app_entry)
            await session.commit()

            print(f"Successfully inserted user_id={user_id}, job_id={job_id} into succ_app table.")
        except Exception as e:
            print(f"Failed to insert into succ_app table: {e}")
            await session.rollback()
        finally:
            # Close the session explicitly
            await session.close()


# Example usage
if __name__ == "__main__":
    # Uncomment the line you want to execute
    #asyncio.run(fetch_all_succ_app())
    #asyncio.run(fetch_all_jobs())
    asyncio.run(insert_single_row_in_succ_app(user_id=4, job_id=619))
