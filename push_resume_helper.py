import json
from app.core.mongo import resumes_collection
import asyncio

import json
from app.core.mongo import resumes_collection

async def add_resume_from_file(json_file_path: str):
    """
    Reads a JSON file from the specified path and inserts its content into the resumes collection.
    
    Args:
        json_file_path (str): The path to the JSON file containing the resume data.
        
    Returns:
        inserted_id (ObjectId): The ID of the inserted document.
    """
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
    
async def main():
    resume_id = await add_resume_from_file("resume.json")
    print(f"Inserted resume with ID: {resume_id}")

asyncio.run(main())
