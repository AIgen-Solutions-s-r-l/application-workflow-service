from pydantic import BaseModel, Field

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
    user_id: str = Field(..., description="The ID of the user submitting the application.")
    jobs: list[JobItem] = Field(
        ..., description="List of jobs to apply to, each represented as a JobItem."
    )