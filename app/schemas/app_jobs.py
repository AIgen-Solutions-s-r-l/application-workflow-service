"""
Request and response schemas for job application endpoints.
"""
import base64
import json
from typing import Any, Dict, Generic, List, Optional, TypeVar
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

from app.models.job import JobData
from app.models.application import ApplicationStatus, ApplicationStatusResponse, ApplicationSubmitResponse


# Re-export for backward compatibility
__all__ = [
    'JobApplicationRequest',
    'DetailedJobData',
    'ApplicationStatusResponse',
    'ApplicationSubmitResponse',
    'PaginationParams',
    'PaginatedResponse',
]


class JobApplicationRequest(BaseModel):
    """
    Request model for receiving the job application data.
    """
    jobs: list[JobData] = Field(
        ..., description="List of jobs to apply to, each represented as a JobItem."
    )


class DetailedJobData(BaseModel):
    """
    Response model for detailed job information including resume and cover letter.
    """
    resume_optimized: Optional[Dict[str, Any]] = None
    cover_letter: Optional[Dict[str, Any]] = None


class PaginationParams(BaseModel):
    """
    Parameters for cursor-based pagination.
    """
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of items to return (1-100)"
    )
    cursor: Optional[str] = Field(
        default=None,
        description="Cursor for pagination (base64 encoded)"
    )

    @staticmethod
    def encode_cursor(last_id: str) -> str:
        """
        Encode a cursor from the last document ID.

        Args:
            last_id: The MongoDB ObjectId string of the last document.

        Returns:
            Base64-encoded cursor string.
        """
        cursor_data = {"id": last_id}
        return base64.urlsafe_b64encode(
            json.dumps(cursor_data).encode()
        ).decode()

    @staticmethod
    def decode_cursor(cursor: str) -> Optional[Dict[str, str]]:
        """
        Decode a cursor to get the last document ID.

        Args:
            cursor: Base64-encoded cursor string.

        Returns:
            Dict with 'id' key or None if invalid.
        """
        try:
            decoded = base64.urlsafe_b64decode(cursor.encode())
            return json.loads(decoded)
        except (ValueError, json.JSONDecodeError):
            return None


class PaginationInfo(BaseModel):
    """
    Pagination metadata in response.
    """
    limit: int = Field(..., description="Number of items per page")
    next_cursor: Optional[str] = Field(None, description="Cursor for next page")
    has_more: bool = Field(..., description="Whether more items exist")
    total_count: Optional[int] = Field(None, description="Total count of items (if available)")


# Generic type for paginated data
T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic paginated response wrapper.
    """
    data: Dict[str, Any] = Field(..., description="Paginated data keyed by ID")
    pagination: PaginationInfo = Field(..., description="Pagination metadata")

    class Config:
        arbitrary_types_allowed = True


class PaginatedJobsResponse(BaseModel):
    """
    Paginated response for job applications.
    """
    data: Dict[str, JobData] = Field(..., description="Job applications keyed by ID")
    pagination: PaginationInfo = Field(..., description="Pagination metadata")
