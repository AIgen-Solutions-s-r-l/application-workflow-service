"""
Application uploader service for managing job application submissions.
"""
from datetime import datetime
from typing import Optional

from app.core.config import settings
from app.core.mongo import applications_collection
from app.core.exceptions import DatabaseOperationError
from app.models.application import ApplicationStatus
from app.services.notification_service import NotificationPublisher
from app.services.queue_service import application_queue_service


notification_publisher = NotificationPublisher()


class ApplicationUploaderService:
    """
    Service for managing job application submissions and status updates.
    """

    async def insert_application_jobs(
        self,
        user_id: str,
        job_list_to_apply: list,
        cv_id: str = None,
        style: str = None
    ) -> str:
        """
        Insert a new application with initial 'pending' status.

        Args:
            user_id: The ID of the user applying for jobs.
            job_list_to_apply: List of jobs the user is applying for (dicts).
            cv_id: Optional reference to uploaded CV document.
            style: Optional resume style preference.

        Returns:
            The ID of the newly inserted application document.

        Raises:
            DatabaseOperationError: If there is an issue inserting the application.
        """
        try:
            # If a CV was uploaded, add "gen_cv": False to each job
            if cv_id:
                for job in job_list_to_apply:
                    job["gen_cv"] = False

            now = datetime.utcnow()

            # Create application document with status tracking
            application_doc = {
                "user_id": user_id,
                "jobs": job_list_to_apply,
                "status": ApplicationStatus.PENDING.value,
                "created_at": now,
                "updated_at": now,
                "processed_at": None,
                "sent": False,
                "retries_left": 5,
                "cv_id": cv_id,
                "style": style,
                "error_reason": None
            }

            result = await applications_collection.insert_one(application_doc)
            application_id = str(result.inserted_id) if result.inserted_id else None

            if application_id:
                await notification_publisher.publish_application_submitted(
                    application_id=application_id,
                    user_id=str(user_id),
                    job_count=len(job_list_to_apply)
                )

                # Publish to processing queue if async processing is enabled
                if settings.async_processing_enabled:
                    await application_queue_service.publish_application_for_processing(
                        application_id=application_id,
                        user_id=str(user_id),
                        job_count=len(job_list_to_apply),
                        cv_id=cv_id,
                        style=style
                    )

            return application_id

        except Exception as e:
            raise DatabaseOperationError(f"Error inserting application data: {str(e)}")

    async def update_application_status(
        self,
        application_id: str,
        status: ApplicationStatus,
        error_reason: Optional[str] = None
    ) -> bool:
        """
        Update the status of an application.

        Args:
            application_id: The ID of the application to update.
            status: The new status.
            error_reason: Optional error message if status is FAILED.

        Returns:
            True if update was successful, False otherwise.

        Raises:
            DatabaseOperationError: If there is an issue updating the application.
        """
        try:
            from bson import ObjectId

            now = datetime.utcnow()
            update_doc = {
                "$set": {
                    "status": status.value,
                    "updated_at": now
                }
            }

            # Set processed_at for terminal states
            if status in (ApplicationStatus.SUCCESS, ApplicationStatus.FAILED):
                update_doc["$set"]["processed_at"] = now

            # Set error_reason if provided
            if error_reason and status == ApplicationStatus.FAILED:
                update_doc["$set"]["error_reason"] = error_reason

            result = await applications_collection.update_one(
                {"_id": ObjectId(application_id)},
                update_doc
            )

            if result.modified_count > 0:
                # Fetch user_id for notification
                doc = await applications_collection.find_one(
                    {"_id": ObjectId(application_id)},
                    {"user_id": 1, "jobs": 1}
                )
                if doc:
                    await notification_publisher.publish_status_changed(
                        application_id=application_id,
                        user_id=str(doc.get("user_id")),
                        status=status.value,
                        job_count=len(doc.get("jobs", []))
                    )

            return result.modified_count > 0

        except Exception as e:
            raise DatabaseOperationError(f"Error updating application status: {str(e)}")

    async def get_application_status(
        self,
        application_id: str,
        user_id: str
    ) -> Optional[dict]:
        """
        Get the status of an application.

        Args:
            application_id: The ID of the application.
            user_id: The ID of the user (for authorization).

        Returns:
            Application status dict or None if not found.

        Raises:
            DatabaseOperationError: If there is an issue querying the application.
        """
        try:
            from bson import ObjectId

            doc = await applications_collection.find_one(
                {"_id": ObjectId(application_id), "user_id": user_id},
                {
                    "status": 1,
                    "created_at": 1,
                    "updated_at": 1,
                    "processed_at": 1,
                    "jobs": 1,
                    "error_reason": 1
                }
            )

            if not doc:
                return None

            return {
                "application_id": str(doc["_id"]),
                "status": doc.get("status", ApplicationStatus.PENDING.value),
                "created_at": doc.get("created_at"),
                "updated_at": doc.get("updated_at"),
                "processed_at": doc.get("processed_at"),
                "job_count": len(doc.get("jobs", [])),
                "error_reason": doc.get("error_reason")
            }

        except Exception as e:
            raise DatabaseOperationError(f"Error getting application status: {str(e)}")
