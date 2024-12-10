import asyncio
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.job import SuccApp
from sqlalchemy.future import select
from app.core.database import get_db
from app.models.job import Job

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
    asyncio.run(fetch_all_jobs())
    #asyncio.run(insert_single_row_in_succ_app(user_id=5, job_id=620))