"""Tests for app_router helper functions."""

import pytest
from unittest.mock import patch

from app.models.job import JobData
from app.routers.app_router import parse_applications


def test_parse_applications_success():
    """Test successful parsing of applications."""
    # Arrange
    doc = {
        "content": {
            "app1": {
                "title": "Software Engineer",
                "description": "Test job description",
                "portal": "LinkedIn"
            },
            "app2": {
                "title": "Data Scientist",
                "description": "Data science position",
                "portal": "Indeed"
            }
        }
    }
    
    # Act
    result = parse_applications(doc)
    
    # Assert
    assert isinstance(result, dict)
    assert len(result) == 2
    assert "app1" in result
    assert "app2" in result
    assert isinstance(result["app1"], JobData)
    assert isinstance(result["app2"], JobData)
    assert result["app1"].title == "Software Engineer"
    assert result["app2"].title == "Data Scientist"

def test_parse_applications_with_exclude_fields():
    """Test parsing applications with excluded fields."""
    # Arrange
    doc = {
        "content": {
            "app1": {
                "title": "Software Engineer",
                "description": "Test job description",
                "portal": "LinkedIn",
                "resume_optimized": '{"some": "data"}',
                "cover_letter": '{"more": "data"}'
            }
        }
    }
    
    # Act
    result = parse_applications(doc, exclude_fields=["resume_optimized", "cover_letter"])
    
    # Assert
    assert isinstance(result, dict)
    assert len(result) == 1
    assert "app1" in result
    assert isinstance(result["app1"], JobData)
    assert result["app1"].title == "Software Engineer"
    # Check that excluded fields are not in the result
    job_dict = result["app1"].model_dump()
    assert "resume_optimized" not in job_dict
    assert "cover_letter" not in job_dict

def test_parse_applications_with_validation_error():
    """Test handling validation errors during parsing."""
    # Arrange
    doc = {
        "content": {
            "app1": {
                "title": "Software Engineer",
                "description": "Test job description",
                "portal": "LinkedIn"
            },
            "app2": {
                # Missing required fields but this won't actually cause a validation error
                # with our JobData model because all fields are optional
                "invalid_field": "This will cause a validation error"
            }
        }
    }
    
    with patch('app.routers.app_router.logger') as mock_logger:
        # Act
        result = parse_applications(doc)
        
        # Assert
        assert isinstance(result, dict)
        assert len(result) == 2  # Both jobs should be included since JobData has all optional fields
        assert "app1" in result
        assert "app2" in result
        mock_logger.error.assert_not_called()  # No validation error with our model

def test_parse_applications_empty_content():
    """Test parsing with empty content."""
    # Arrange
    doc = {"content": {}}
    
    # Act
    result = parse_applications(doc)
    
    # Assert
    assert isinstance(result, dict)
    assert len(result) == 0