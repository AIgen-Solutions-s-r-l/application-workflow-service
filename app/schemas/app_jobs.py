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

class JobResponse(BaseModel):
    """
    Response model for job details including all available fields.
    """
    id: Optional[str] = Field(None, description="Unique identifier (UUID) for the job")
    job_id: int = Field(..., description="The ID of the job")
    title: str = Field(..., description="The title of the job")
    is_remote: Optional[bool] = Field(None, description="Whether the job is remote")
    workplace_type: Optional[str] = Field(None, description="Type of workplace (e.g., remote, hybrid, onsite)")
    posted_date: Optional[datetime] = Field(None, description="When the job was posted")
    job_state: Optional[str] = Field(None, description="Current state of the job")
    description: Optional[str] = Field(None, description="Full job description")
    short_description: Optional[str] = Field(None, description="Brief description of the job")
    processed_description: Optional[str] = Field(None, description="Processed version of the job description")
    apply_link: Optional[str] = Field(None, description="URL to apply for the job")
    field: Optional[str] = Field(None, description="Field or industry of the job")
    experience: Optional[str] = Field(None, description="Required experience level")
    skills_required: Optional[list[str]] = Field(None, description="List of required skills")
    company_id: int = Field(..., description="ID of the company offering the job")
    location_id: int = Field(..., description="ID of the job location")
    cluster_id: Optional[int] = Field(None, description="ID of the job cluster")
    embedding: Optional[list[float]] = Field(None, description="Vector embedding of the job")
    sparse_embeddings: Optional[list[float]] = Field(None, description="Sparse vector embeddings of the job")

    class Config:
        from_attributes = True

# TODO: add other fields!
class JobData(BaseModel):
    job_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    portal: Optional[str] = None

class DetailedJobData(BaseModel):
    resume_optimized: Optional[str] = None
    cover_letter: Optional[str] = None