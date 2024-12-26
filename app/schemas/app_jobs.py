from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class JobItem(BaseModel):
    """
    Model for individual job details.
    """
    job_id: int = Field(..., description="The ID of the job.")
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

# Useful when we'll have all the fields!
'''class JobResponse(BaseModel):
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
        from_attributes = True'''

# TODO: add other fields!
class JobData(BaseModel):
    job_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    portal: Optional[str] = None

class DetailedJobData(BaseModel):
    resume_optimized: Optional[str] = None
    cover_letter: Optional[str] = None