from app.core.mongo import applications_collection
from app.core.exceptions import DatabaseOperationError
from app.services.notification_service import NotificationPublisher
from app.core.rabbitmq_client import Settings

settings = Settings()

notification_publisher = NotificationPublisher(settings=settings)

class ApplicationUploaderService:

    async def insert_application_jobs(self, user_id: str, job_list_to_apply: list, cv_id: str = None, style: str = None) -> str:
        """
        Upsert the application data: if a document for the user does not exist, create it.
        If it exists, add the new jobs to the existing jobs array.

        Args:
            user_id (str): The ID of the user applying for jobs.
            job_list_to_apply (list): List of jobs the user is applying for (dicts).
            is_cv (bool): Whether the application includes a CV upload.

        Returns:
            str or None: The ID of the newly inserted application document.
                         (If the document was updated rather than newly inserted,
                          this may return None, depending on your logic.)

        Raises:
            DatabaseOperationError: If there is an issue upserting the application to the database.
        """
        try:
            # If a CV was uploaded, add "gen_cv": False to each job
            if cv_id:
                for job in job_list_to_apply:
                    job["gen_cv"] = False

            # Perform the upsert or insert operation
            # (In this simple example, we are using .insert_one() — 
            #  adjust your logic if you truly want an upsert.)
            result = await applications_collection.insert_one(
                {
                    "user_id": user_id,
                    "jobs": job_list_to_apply,
                    "sent": False,
                    "retries_left": 5,
                    "cv_id": cv_id,
                    "style": style
                }
            )

            await notification_publisher.publish_application_updated()
            
            # If a new document was created, inserted_id will hold the new _id
            return str(result.inserted_id) if result.inserted_id else None

        except Exception as e:
            raise DatabaseOperationError(f"Error upserting application data: {str(e)}")