"""
Application submission load test tasks.
"""

import json
import random
import uuid
from pathlib import Path

from locust import HttpUser


class ApplicationTasks:
    """Tasks for application submission endpoints."""

    # Sample job data templates
    JOB_TEMPLATES = [
        {
            "title": "Software Engineer",
            "description": "Develop and maintain software applications",
            "portal": "LinkedIn",
            "company": "Tech Corp",
            "location": "San Francisco, CA",
        },
        {
            "title": "Data Scientist",
            "description": "Analyze data and build ML models",
            "portal": "Indeed",
            "company": "Data Inc",
            "location": "New York, NY",
        },
        {
            "title": "DevOps Engineer",
            "description": "Manage CI/CD pipelines and infrastructure",
            "portal": "Glassdoor",
            "company": "Cloud Systems",
            "location": "Seattle, WA",
        },
        {
            "title": "Product Manager",
            "description": "Lead product development and strategy",
            "portal": "LinkedIn",
            "company": "Product Labs",
            "location": "Austin, TX",
        },
        {
            "title": "Frontend Developer",
            "description": "Build responsive web applications",
            "portal": "AngelList",
            "company": "Startup XYZ",
            "location": "Remote",
        },
    ]

    @classmethod
    def generate_job(cls) -> dict:
        """Generate a random job posting."""
        template = random.choice(cls.JOB_TEMPLATES)
        return {
            **template,
            "id": str(uuid.uuid4()),
            "description": f"{template['description']} - {uuid.uuid4().hex[:8]}",
        }

    @classmethod
    def generate_jobs(cls, count: int = None) -> list:
        """Generate a list of random jobs."""
        if count is None:
            count = random.randint(1, 5)
        return [cls.generate_job() for _ in range(count)]

    @classmethod
    def submit(cls, client: HttpUser, with_resume: bool = False) -> dict | None:
        """
        Submit a new application.

        Args:
            client: Locust HTTP client.
            with_resume: Whether to include a PDF resume.

        Returns:
            Response data if successful, None otherwise.
        """
        jobs = cls.generate_jobs()
        jobs_payload = json.dumps({"jobs": jobs})

        data = {
            "jobs": jobs_payload,
            "style": random.choice(["professional", "modern", "classic", None]),
        }

        files = None
        if with_resume:
            # Use a minimal valid PDF for testing
            pdf_content = cls._get_sample_pdf()
            files = {"cv": ("resume.pdf", pdf_content, "application/pdf")}

        with client.post(
            "/applications",
            data=data,
            files=files,
            name="POST /applications",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                return response.json()
            elif response.status_code == 429:
                # Rate limited - mark as expected
                response.success()
                return None
            else:
                response.failure(f"Status {response.status_code}: {response.text[:100]}")
                return None

    @classmethod
    def submit_batch(cls, client: HttpUser, batch_size: int = 5) -> dict | None:
        """
        Submit a batch of applications.

        Args:
            client: Locust HTTP client.
            batch_size: Number of applications in batch.

        Returns:
            Response data if successful, None otherwise.
        """
        items = []
        for _ in range(batch_size):
            items.append({
                "jobs": cls.generate_jobs(random.randint(1, 3)),
                "style": random.choice(["professional", "modern", "classic"]),
            })

        with client.post(
            "/batch/applications",
            data={"items": json.dumps(items)},
            name="POST /batch/applications",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                return response.json()
            elif response.status_code == 429:
                response.success()
                return None
            else:
                response.failure(f"Status {response.status_code}")
                return None

    @classmethod
    def _get_sample_pdf(cls) -> bytes:
        """Get sample PDF content for testing."""
        # Check if sample file exists
        sample_path = Path(__file__).parent.parent / "data" / "sample_resume.pdf"
        if sample_path.exists():
            return sample_path.read_bytes()

        # Return minimal valid PDF
        return b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >> endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer << /Size 4 /Root 1 0 R >>
startxref
196
%%EOF"""
