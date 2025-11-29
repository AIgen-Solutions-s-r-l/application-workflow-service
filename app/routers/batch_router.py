"""
Batch operations router for handling multiple applications at once.

Provides endpoints for:
- Batch submission of applications
- Batch status tracking
- Batch cancellation
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.core.exceptions import DatabaseOperationError
from app.services.batch_service import (
    batch_service,
    BatchItem,
    BatchResponse,
    BatchStatusResponse
)
from app.services.pdf_resume_service import PdfResumeService

router = APIRouter(prefix="/batch", tags=["batch"])

pdf_resume_service = PdfResumeService()


class BatchSubmitRequest(BaseModel):
    """Request body for batch submission."""
    items: list[BatchItem] = Field(
        ...,
        description="List of application items to submit",
        min_length=1,
        max_length=100
    )


@router.post(
    "/applications",
    summary="Submit multiple applications in batch",
    description=(
        "Submit multiple job applications at once. Each item can have its own jobs and style. "
        "A shared CV can be uploaded for all applications. "
        "Returns immediately with a batch_id for tracking progress."
    ),
    response_model=BatchResponse
)
async def submit_batch(
    items: str = Form(..., description="JSON array of batch items"),
    cv: Optional[UploadFile] = File(None, description="Optional shared PDF resume"),
    current_user=Depends(get_current_user)
):
    """
    Submit a batch of job applications.

    Args:
        items: JSON string of BatchItem list.
        cv: Optional shared PDF resume for all applications.
        current_user: Authenticated user ID.

    Returns:
        BatchResponse with batch_id and initial status.
    """
    import json

    user_id = current_user

    # Parse items
    try:
        items_data = json.loads(items)
        if not isinstance(items_data, list):
            raise ValueError("items must be a list")

        batch_items = [BatchItem(**item) for item in items_data]

        if len(batch_items) > 100:
            raise HTTPException(
                status_code=400,
                detail="Maximum 100 items per batch"
            )

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid batch items: {str(e)}"
        )

    # Handle CV upload
    cv_id = None
    if cv is not None:
        if cv.content_type != "application/pdf":
            raise HTTPException(
                status_code=400,
                detail="Uploaded file must be a PDF"
            )

        try:
            pdf_bytes = await cv.read()
            cv_id = await pdf_resume_service.store_pdf_resume(pdf_bytes)
        except DatabaseOperationError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to store PDF resume: {str(e)}"
            )

    # Create batch
    try:
        response = await batch_service.create_batch(
            user_id=user_id,
            items=batch_items,
            cv_id=cv_id
        )
        return response

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create batch: {str(e)}"
        )


@router.get(
    "/applications/{batch_id}",
    summary="Get batch status",
    description="Get the current status and progress of a batch submission.",
    response_model=BatchStatusResponse
)
async def get_batch_status(
    batch_id: str,
    current_user=Depends(get_current_user)
):
    """
    Get the status of a batch submission.

    Args:
        batch_id: The batch ID to query.
        current_user: Authenticated user ID.

    Returns:
        BatchStatusResponse with current status and results.
    """
    status = await batch_service.get_batch_status(
        batch_id=batch_id,
        user_id=current_user
    )

    if not status:
        raise HTTPException(
            status_code=404,
            detail="Batch not found"
        )

    return status


@router.delete(
    "/applications/{batch_id}",
    summary="Cancel a batch",
    description="Cancel a pending or processing batch. Completed batches cannot be cancelled."
)
async def cancel_batch(
    batch_id: str,
    current_user=Depends(get_current_user)
):
    """
    Cancel a batch submission.

    Args:
        batch_id: The batch ID to cancel.
        current_user: Authenticated user ID.

    Returns:
        Success message if cancelled.
    """
    success = await batch_service.cancel_batch(
        batch_id=batch_id,
        user_id=current_user
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot cancel batch (not found, not owned, or already completed)"
        )

    return {"message": "Batch cancelled", "batch_id": batch_id}
