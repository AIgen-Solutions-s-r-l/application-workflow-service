from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class JobItem(BaseModel):
    """
    Model for individual job details.
    """
    description: str = Field(..., description="Description of the job.")
    portal: str = Field(..., description="The portal where the job was found.")
    title: str = Field(..., description="The title of the job.")

class JobApplicationRequest(BaseModel):
    """
    Request model for receiving the job application data.
    """
    jobs: list[JobItem] = Field(
        ..., description="List of jobs to apply to, each represented as a JobItem."
    )

class JobResponse(BaseModel):
    job_id: int
    title: str
    is_remote: Optional[bool]
    workplace_type: Optional[str]
    posted_date: Optional[datetime]
    job_state: Optional[str]
    description: Optional[str]
    apply_link: Optional[str]
    company_id: int
    location_id: int

    class Config:
        from_attributes = True