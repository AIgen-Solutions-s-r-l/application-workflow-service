import pytest
from unittest.mock import AsyncMock, patch
from app.services.resume_ops import get_resume_by_user_id, save_application_with_resume
import json

# Define add_resume_from_file directly in the test file
async def add_resume_from_file(json_file_path: str):
    """
    Reads a JSON file from the specified path and inserts its content into the resumes collection.
    
    Args:
        json_file_path (str): The path to the JSON file containing the resume data.
        
    Returns:
        inserted_id (ObjectId): The ID of the inserted document.
    """
    from app.core.mongo import resumes_collection
    try:
        # Load resume data from the JSON file
        with open(json_file_path, 'r') as file:
            data = json.load(file)
        
        # Ensure JSON has a list structure as per your example
        if isinstance(data, list) and data:
            # Extract user_id and treat the rest as resume data
            document = {
                "user_id": data[0].get("user_id"),
                "resume": data[0]  # Treat entire object as the resume
            }
            
            # Validate user_id presence
            if document["user_id"] is None:
                raise ValueError("JSON file must contain 'user_id' field in each entry.")
            
            # Insert into MongoDB
            result = await resumes_collection.insert_one(document)
            return result.inserted_id

        else:
            raise ValueError("JSON file must contain a list with resume entries.")
    
    except Exception as e:
        print(f"An error occurred while adding the resume: {e}")
        return None

# Test for get_resume_by_user_id function
@pytest.mark.asyncio
async def test_get_resume_by_user_id():
    user_id = "1"
    resume_data = {"user_id": user_id, "resume": {"experience": "3 years"}}
    
    with patch("app.services.resume_ops.resumes_collection.find_one", AsyncMock(return_value=resume_data)):
        resume = await get_resume_by_user_id(user_id)
        assert resume == resume_data["resume"]

@pytest.mark.asyncio
async def test_get_resume_by_user_id_not_found():
    user_id = "999"
    
    with patch("app.services.resume_ops.resumes_collection.find_one", AsyncMock(return_value=None)):
        resume = await get_resume_by_user_id(user_id)
        assert resume is None

# Test for save_application_with_resume function
@pytest.mark.asyncio
async def test_save_application_with_resume():
    user_id = "1"
    resume = {"experience": "3 years"}
    job_list = [{"job_id": "job1"}, {"job_id": "job2"}]
    
    mock_insert_result = AsyncMock()
    mock_insert_result.inserted_id = "mock_id"

    with patch("app.services.resume_ops.applications_collection.insert_one", AsyncMock(return_value=mock_insert_result)):
        application_id = await save_application_with_resume(user_id, resume, job_list)
        assert application_id == "mock_id"

# Test for add_resume_from_file function
@pytest.mark.asyncio
async def test_add_resume_from_file(tmp_path):
    json_content = [
        {
            "user_id": "1",
            "achievements": [{"name": "Top Performer", "description": "Excellent performance"}]
        }
    ]
    json_file = tmp_path / "resume.json"
    json_file.write_text(json.dumps(json_content))

    mock_insert_result = AsyncMock()
    mock_insert_result.inserted_id = "mock_id"
    
    with patch("app.core.mongo.resumes_collection.insert_one", AsyncMock(return_value=mock_insert_result)):
        application_id = await add_resume_from_file(str(json_file))
        assert application_id == "mock_id"