import pytest
from unittest.mock import AsyncMock, patch
from app.services.pdf_resume_service import PdfResumeService
from app.core.exceptions import DatabaseOperationError

@pytest.mark.asyncio
async def test_store_pdf_resume_success(mock_pdf_resumes_collection, sample_pdf_bytes):
    """Test successful storage of a PDF resume."""
    # Arrange
    service = PdfResumeService()
    
    # Configure the mock to properly handle await
    mock_pdf_resumes_collection.insert_one = AsyncMock()
    mock_pdf_resumes_collection.insert_one.return_value.inserted_id = "mocked_pdf_id"
    
    # Act
    result = await service.store_pdf_resume(sample_pdf_bytes)
    
    # Assert
    assert result == "mocked_pdf_id"
    mock_pdf_resumes_collection.insert_one.assert_called_once_with({
        "cv": sample_pdf_bytes,
        "app_ids": []
    })

@pytest.mark.asyncio
async def test_store_pdf_resume_empty_pdf(mock_pdf_resumes_collection):
    """Test storing an empty PDF."""
    # Arrange
    service = PdfResumeService()
    empty_pdf = b""
    
    # Configure the mock to properly handle await
    mock_pdf_resumes_collection.insert_one = AsyncMock()
    mock_pdf_resumes_collection.insert_one.return_value.inserted_id = "mocked_pdf_id"
    
    # Act
    result = await service.store_pdf_resume(empty_pdf)
    
    # Assert
    assert result == "mocked_pdf_id"
    mock_pdf_resumes_collection.insert_one.assert_called_once_with({
        "cv": empty_pdf,
        "app_ids": []
    })

@pytest.mark.asyncio
async def test_store_pdf_resume_database_error(mock_pdf_resumes_collection, sample_pdf_bytes):
    """Test error handling when database operation fails."""
    # Arrange
    # Configure the mock to properly handle await and raise an exception
    mock_pdf_resumes_collection.insert_one = AsyncMock(side_effect=Exception("Database error"))
    
    service = PdfResumeService()
    
    # Act & Assert
    with pytest.raises(DatabaseOperationError) as exc_info:
        await service.store_pdf_resume(sample_pdf_bytes)
    
    # Verify error message
    assert "Error storing pdf resume data" in str(exc_info.value)
    assert "Database error" in str(exc_info.value)

@pytest.mark.asyncio
async def test_store_pdf_resume_returns_none_on_missing_inserted_id(mock_pdf_resumes_collection, sample_pdf_bytes):
    """Test handling when the database doesn't return an inserted_id."""
    # Arrange
    # Configure the mock to properly handle await but return None for inserted_id
    mock_pdf_resumes_collection.insert_one = AsyncMock()
    mock_pdf_resumes_collection.insert_one.return_value.inserted_id = None
    
    service = PdfResumeService()
    
    # Act
    result = await service.store_pdf_resume(sample_pdf_bytes)
    
    # Assert
    assert result is None
    mock_pdf_resumes_collection.insert_one.assert_called_once()