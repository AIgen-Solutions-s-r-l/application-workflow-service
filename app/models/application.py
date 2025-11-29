"""
Application models for job application workflow.

This module defines the core data models for tracking application status
throughout the processing lifecycle.
"""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ApplicationStatus(str, Enum):
    """
    Enum representing the possible states of a job application.

    Lifecycle: pending -> processing -> success/failed
    """
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class Application(BaseModel):
    """
    Model representing a job application document in MongoDB.

    This model tracks the full lifecycle of a batch of job applications
    submitted by a user.
    """
    id: str | None = Field(None, alias="_id", description="MongoDB document ID")
    user_id: str = Field(..., description="The ID of the user who submitted the application")
    jobs: list[dict] = Field(default_factory=list, description="List of jobs to apply for")
    status: ApplicationStatus = Field(
        default=ApplicationStatus.PENDING,
        description="Current status of the application batch"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the application was created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the application was last updated"
    )
    processed_at: datetime | None = Field(
        None,
        description="Timestamp when the application reached a terminal state (success/failed)"
    )

    # Processing metadata
    sent: bool = Field(default=False, description="Whether the application has been sent for processing")
    retries_left: int = Field(default=5, description="Number of retry attempts remaining")
    cv_id: str | None = Field(None, description="Reference to uploaded CV document")
    style: str | None = Field(None, description="Resume style preference")
    error_reason: str | None = Field(
        None,
        description="Error message if application failed"
    )

    class Config:
        from_attributes = True
        populate_by_name = True
        use_enum_values = True


class ApplicationStatusResponse(BaseModel):
    """
    Response model for application status queries.
    """
    application_id: str = Field(..., description="The application ID")
    status: ApplicationStatus = Field(..., description="Current status")
    created_at: datetime = Field(..., description="When the application was created")
    updated_at: datetime = Field(..., description="When the application was last updated")
    processed_at: datetime | None = Field(None, description="When processing completed")
    job_count: int = Field(..., description="Number of jobs in this application")
    error_reason: str | None = Field(None, description="Error message if failed")

    class Config:
        use_enum_values = True


class ApplicationSubmitResponse(BaseModel):
    """
    Response model for application submission.
    """
    application_id: str = Field(..., description="The created application ID")
    status: ApplicationStatus = Field(..., description="Initial status (pending)")
    status_url: str = Field(..., description="URL to check application status")
    job_count: int = Field(..., description="Number of jobs submitted")
    created_at: datetime = Field(..., description="When the application was created")

    class Config:
        use_enum_values = True
