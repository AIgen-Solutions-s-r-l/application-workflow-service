
from pydantic import BaseModel, Field


class JobData(BaseModel):
    """
    Model for job details in a response.
    """
    id: str | None = Field(None, description="The unique ID of the job record.")
    portal: str | None = Field(None, description="The portal where the job was found.")
    title: str | None = Field(None, description="The title of the job.")
    workplace_type: str | None = Field(None, description="The workplace type, e.g., onsite, remote, or hybrid.")
    posted_date: str | None = Field(None, description="The date the job was posted.")
    job_state: str | None = Field(None, description="The state or status of the job.")
    description: str | None = Field(None, description="A detailed description of the job.")
    apply_link: str | None = Field(None, description="The link to apply for the job.")
    company_name: str | None = Field(None, description="The name of the company offering the job.")
    location: str | None = Field(None, description="The location of the job.")
    short_description: str | None = Field(None, description="A short description of the job.")
    field: str | None = Field(None, description="The field or industry of the job.")
    company_logo: str | None = Field(None, description="The URL of the company logo.")
    experience: str | None = Field(None, description="The required experience for the job.")
    skills_required: list[str] | None = Field(None, description="The required skills for the job.")

    class Config:
        from_attributes = True
