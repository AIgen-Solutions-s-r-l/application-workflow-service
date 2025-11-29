# app/services/pdf_resume_service.py

from app.core.exceptions import DatabaseOperationError
from app.core.mongo import pdf_resumes_collection


class PdfResumeService:
    """
    Handles inserting or updating PDF resumes into the `pdf_resumes` collection.
    """

    async def store_pdf_resume(self, pdf_bytes: bytes) -> str:
        """
        Inserts a PDF resume into the collection with an empty `app_ids` array.

        Args:
            pdf_bytes (bytes): Binary data of the PDF file.

        Returns:
            str: The newly inserted document's ID.

        Raises:
            DatabaseOperationError: If there is an issue inserting the PDF resume.
        """
        try:
            result = await pdf_resumes_collection.insert_one({"cv": pdf_bytes, "app_ids": []})
            return str(result.inserted_id) if result.inserted_id else None
        except Exception as e:
            raise DatabaseOperationError(f"Error storing pdf resume data: {str(e)}")
