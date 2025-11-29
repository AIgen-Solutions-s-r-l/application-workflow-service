"""
Export router for downloading application data.

Provides endpoints for:
- CSV export
- Excel export
- Export summary
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

from app.core.auth import get_current_user
from app.services.export_service import export_service

router = APIRouter(prefix="/export", tags=["export"])


@router.get(
    "/summary",
    summary="Get export summary",
    description="Get a summary of available data for export, including counts and filter options.",
)
async def get_export_summary(current_user=Depends(get_current_user)):
    """
    Get export summary for the authenticated user.

    Args:
        current_user: Authenticated user ID.

    Returns:
        Export summary with counts and available filters.
    """
    return await export_service.get_export_summary(user_id=current_user)


@router.get(
    "/csv",
    summary="Export applications to CSV",
    description=(
        "Download all applications as a CSV file. "
        "Supports filtering by status, portal, and date range."
    ),
)
async def export_csv(
    current_user=Depends(get_current_user),
    include_successful: bool = Query(default=True, description="Include successful applications"),
    include_failed: bool = Query(default=True, description="Include failed applications"),
    portal: str | None = Query(default=None, description="Filter by portal"),
    date_from: datetime | None = Query(default=None, description="Filter from date (ISO 8601)"),
    date_to: datetime | None = Query(default=None, description="Filter until date (ISO 8601)"),
    stream: bool = Query(default=False, description="Use streaming for large exports"),
):
    """
    Export applications to CSV format.

    Args:
        current_user: Authenticated user ID.
        include_successful: Whether to include successful applications.
        include_failed: Whether to include failed applications.
        portal: Optional portal filter.
        date_from: Optional start date filter.
        date_to: Optional end date filter.
        stream: Whether to use streaming response.

    Returns:
        CSV file download.
    """
    filename = f"applications_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

    if stream:
        # Streaming response for large datasets
        async def generate():
            async for chunk in export_service.export_to_csv_stream(
                user_id=current_user,
                include_successful=include_successful,
                include_failed=include_failed,
                portal_filter=portal,
                date_from=date_from,
                date_to=date_to,
            ):
                yield chunk

        return StreamingResponse(
            generate(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    # Regular response for smaller datasets
    csv_content = await export_service.export_to_csv(
        user_id=current_user,
        include_successful=include_successful,
        include_failed=include_failed,
        portal_filter=portal,
        date_from=date_from,
        date_to=date_to,
    )

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get(
    "/excel",
    summary="Export applications to Excel",
    description=(
        "Download all applications as an Excel file with formatting. "
        "Successful applications are highlighted in green, failed in red. "
        "Supports filtering by status, portal, and date range."
    ),
)
async def export_excel(
    current_user=Depends(get_current_user),
    include_successful: bool = Query(default=True, description="Include successful applications"),
    include_failed: bool = Query(default=True, description="Include failed applications"),
    portal: str | None = Query(default=None, description="Filter by portal"),
    date_from: datetime | None = Query(default=None, description="Filter from date (ISO 8601)"),
    date_to: datetime | None = Query(default=None, description="Filter until date (ISO 8601)"),
):
    """
    Export applications to Excel format.

    Args:
        current_user: Authenticated user ID.
        include_successful: Whether to include successful applications.
        include_failed: Whether to include failed applications.
        portal: Optional portal filter.
        date_from: Optional start date filter.
        date_to: Optional end date filter.

    Returns:
        Excel file download.
    """
    filename = f"applications_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"

    try:
        excel_content = await export_service.export_to_excel(
            user_id=current_user,
            include_successful=include_successful,
            include_failed=include_failed,
            portal_filter=portal,
            date_from=date_from,
            date_to=date_to,
        )

        return Response(
            content=excel_content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate Excel export: {str(e)}")
