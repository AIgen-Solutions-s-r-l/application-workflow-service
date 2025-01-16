from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

class JobResponse(BaseModel):
    """
    Model for job details in a response.
    """
    title: Optional[str] = Field(None, description="The title of the job.")
    is_remote: Optional[bool] = Field(None, description="Indicates if the job is remote.")
    workplace_type: Optional[str] = Field(None, description="The workplace type, e.g., onsite, remote, or hybrid.")
    posted_date: Optional[datetime] = Field(None, description="The date the job was posted.")
    job_state: Optional[str] = Field(None, description="The state or status of the job.")
    description: Optional[str] = Field(None, description="A detailed description of the job.")
    apply_link: Optional[str] = Field(None, description="The link to apply for the job.")
    company_name: Optional[str] = Field(None, description="The name of the company offering the job.")
    location: Optional[str] = Field(None, description="The location of the job.")

    class Config:
        from_attributes = True

class JobData(JobResponse):
    """
    Model representing comprehensive job details.
    """
    id: int = Field(..., description="The unique ID of the job record.")
    job_id: int = Field(..., description="The ID of the job.")
    portal: Optional[str] = Field(None, description="The portal where the job was found.")


class JobApplicationRequest(BaseModel):
    """
    Request model for receiving the job application data.
    """
    jobs: list[JobResponse] = Field(
        ..., description="List of jobs to apply to, each represented as a JobItem."
    )

class DetailedJobData(BaseModel):
    resume_optimized: Optional[str] = None
    cover_letter: Optional[str] = None