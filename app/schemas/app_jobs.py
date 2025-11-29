"""
Request and response schemas for job application endpoints.
"""
import base64
import json
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from app.models.application import (
    ApplicationStatusResponse,
    ApplicationSubmitResponse,
)
from app.models.job import JobData

# Re-export for backward compatibility
__all__ = [
    'JobApplicationRequest',
    'DetailedJobData',
    'ApplicationStatusResponse',
    'ApplicationSubmitResponse',
    'FilterParams',
    'PaginationParams',
    'PaginatedResponse',
    'PaginatedJobsResponse',
    'PaginationInfo',
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
    resume_optimized: dict[str, Any] | None = None
    cover_letter: dict[str, Any] | None = None


class FilterParams(BaseModel):
    """
    Parameters for filtering list endpoints.
    """
    portal: str | None = Field(
        default=None,
        description="Filter by job portal (e.g., 'LinkedIn', 'Indeed')"
    )
    company_name: str | None = Field(
        default=None,
        description="Filter by company name (partial match)"
    )
    title: str | None = Field(
        default=None,
        description="Filter by job title (partial match)"
    )
    date_from: datetime | None = Field(
        default=None,
        description="Filter applications from this date (ISO 8601)"
    )
    date_to: datetime | None = Field(
        default=None,
        description="Filter applications until this date (ISO 8601)"
    )


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
    cursor: str | None = Field(
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
    def decode_cursor(cursor: str) -> dict[str, str] | None:
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
    next_cursor: str | None = Field(None, description="Cursor for next page")
    has_more: bool = Field(..., description="Whether more items exist")
    total_count: int | None = Field(None, description="Total count of items (if available)")


# Generic type for paginated data
T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic paginated response wrapper.
    """
    data: dict[str, Any] = Field(..., description="Paginated data keyed by ID")
    pagination: PaginationInfo = Field(..., description="Pagination metadata")

    class Config:
        arbitrary_types_allowed = True


class PaginatedJobsResponse(BaseModel):
    """
    Paginated response for job applications.
    """
    data: dict[str, JobData] = Field(..., description="Job applications keyed by ID")
    pagination: PaginationInfo = Field(..., description="Pagination metadata")
