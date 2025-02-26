# Application Manager Service

The **Application Manager Service** is a Python-based backend service designed to manage application workflows, handle user resumes, and track job applications. It interacts with MongoDB for data storage and uses FastAPI for API-based interactions.

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Application Workflow](#application-workflow)
- [Running the Application](#running-the-application)
- [Testing](#testing)
- [Folder Structure](#folder-structure)
- [API Endpoints](#api-endpoints)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

The Application Manager Service provides key functionalities such as:
1. **Managing User Applications**: Handles user data and application workflows.
2. **Resume Processing**: Validates and stores resumes for job applications.
3. **Job Application Tracking**: Tracks the progress of applications.

---

## Requirements

- Python 3.12.3
- MongoDB server
- Virtualenv

---

## Installation

1. **Clone the Repository**:

    ```bash
    git clone https://github.com/yourusername/application_manager_service.git
    cd application_manager_service
    ```

2. **Create a Virtual Environment**:

    ```bash
    python -m venv venv
    ```

3. **Activate the Virtual Environment**:

    - On Windows:

        ```bash
        venv\Scripts\activate
        ```

    - On macOS/Linux:

        ```bash
        source venv/bin/activate
        ```

4. **Install Dependencies**:

    ```bash
    pip install -r requirements.txt
    ```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root directory with the following configuration:

```env
SERVICE_NAME=application_manager_service
MONGO_URI=mongodb://localhost:27017/
```

### Database Setup

Run the database initialization scripts to set up MongoDB:

```bash
python run_init_db.py
```

---

## Application Workflow

1. **HTTP API Requests**:
   - Accepts POST requests at `/applications` to handle application data.

2. **Database Management**:
   - Stores user resumes and job application data in MongoDB.

3. **Resume Processing**:
   - Retrieves resumes based on user IDs for application tracking.

4. **Application Submission**:
   - Submits and stores job application details using the provided API endpoint.

---

## Running the Application

Run the application using the following command:

```bash
python app/main.py
```

Ensure MongoDB is running and accessible.

---

## Testing

Run the test suite using:

```bash
pytest
```

### Test Coverage

- **Resume Operations**:
  - Validates resume handling logic (`app/tests/test_resume_ops.py`).

---

## Folder Structure

```plaintext
application_manager_service/
│
├── app/
│   ├── core/               # Core configurations and utilities
│   ├── models/             # Data models for jobs and users
│   ├── routers/            # API endpoint routers
│   ├── scripts/            # Database initialization scripts
│   ├── services/           # Business logic
│   ├── tests/              # Unit and integration tests
│   └── main.py             # Entry point of the application
│
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker setup
├── README.md               # Documentation
└── .env.example            # Example environment variables file
```

---

## API Endpoints

The API provides the following endpoints:

- **Job Applications**:
   - `POST /applications`: Submits a list of jobs to apply for and saves the application data in MongoDB.

Refer to `routers/app_router.py` for additional details on API endpoints.

Curl example (**NOTE** that the cv is OPTIONAL, you can avoid it completely if the user doesn't upload it)
```
curl -X POST "http://localhost:8009/applications" \
-H "Authorization: Bearer <>" \
-H "Content-Type: multipart/form-data" \
-F 'jobs={"jobs":[{"id":"12345678-1234-1234-1234-123456789abc","description":"Boh","portal":"example","title":"FP&A manager"}]}' \
-F 'style=samudum_bold' \
-F 'cv=@/path/to/file.pdf'
```

![Matching 2](https://github.com/user-attachments/assets/deffe9c5-be3d-403e-857e-3bab02429e48)


## User Applications

Our application provides four main endpoints for retrieving user applications (both successful and failed). All endpoints **require** a valid JWT token in the `Authorization` header.

1. **Get All Successful Applications**  
   - **Endpoint**: `GET /applied`  
   - **Description**: Retrieves **all successful** job applications for the authenticated user, **excluding** `resume_optimized` and `cover_letter`.  
   - **Curl Example**:
     ```bash
     curl -X GET "http://localhost:8006/applied" \
     -H "Authorization: Bearer <your_jwt_token>" \
     -H "Content-Type: application/json"
     ```
   - **Response**: A list of jobs in the `Dict[app_id, JobData]` model format.

2. **Get All Failed Applications**  
   - **Endpoint**: `GET /fail_applied`  
   - **Description**: Retrieves **all failed** job applications for the authenticated user, **excluding** `resume_optimized` and `cover_letter`.  
   - **Curl Example**:
     ```bash
     curl -X GET "http://localhost:8006/fail_applied" \
     -H "Authorization: Bearer <your_jwt_token>" \
     -H "Content-Type: application/json"
     ```
   - **Response**: A list of jobs in the `Dict[app_id, JobData]` model format.

3. **Get Detailed Info on a Specific Successful Application**  
   - **Endpoint**: `GET /applied/{app_id}`  
   - **Description**: Retrieves detailed information (**only** `resume_optimized` and `cover_letter`) for a specific successful application.  
   - **Curl Example**:
     ```bash
     curl -X GET "http://localhost:8006/applied/{app_id}" \
     -H "Authorization: Bearer <your_jwt_token>" \
     -H "Content-Type: application/json"
     ```
   - **Response**: A `DetailedJobData` object containing `resume_optimized` and `cover_letter`.

4. **Get Detailed Info on a Specific Failed Application**  
   - **Endpoint**: `GET /fail_applied/{app_id}`  
   - **Description**: Retrieves detailed information (**only** `resume_optimized` and `cover_letter`) for a specific failed application.  
   - **Curl Example**:
     ```bash
     curl -X GET "http://localhost:8006/fail_applied/{app_id}" \
     -H "Authorization: Bearer <your_jwt_token>" \
     -H "Content-Type: application/json"
     ```
   - **Response**: A `DetailedJobData` object containing `resume_optimized` and `cover_letter`.

![SeeApp 5](https://github.com/user-attachments/assets/556bd166-2a75-4aae-b3c0-3da0ded10aa9)


---

## Contributing

1. Fork the repository.
2. Create a feature branch:

    ```bash
    git checkout -b feature-branch
    ```

3. Commit your changes:

    ```bash
    git commit -am 'Add new feature'
    ```

4. Push your branch:

    ```bash
    git push origin feature-branch
    ```

5. Create a Pull Request.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
