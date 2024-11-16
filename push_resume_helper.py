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
            resume_data = json.load(file)
        
        # Ensure required fields are present
        if "user_id" not in resume_data or "resume" not in resume_data:
            raise ValueError("JSON file must contain 'user_id' and 'resume' fields.")
        
        # Insert the resume data into the resumes collection
        result = await resumes_collection.insert_one(resume_data)
        
        return result.inserted_id

    except Exception as e:
        print(f"An error occurred while adding the resume: {e}")
        return None

# main
if __name__ == "__main__":
    json_file_path = "resume.json"
    inserted_id = add_resume_from_file(json_file_path)
    print(f"Inserted resume with ID: {inserted_id}")