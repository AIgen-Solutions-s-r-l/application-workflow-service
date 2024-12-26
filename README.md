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

Curl example:
```
curl -X POST "http://localhost:8006/applications" \
-H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJqb2huZG9lIiwiaWQiOjQsImlzX2FkbWluIjpmYWxzZSwiZXhwIjoxNzMzNTA2NjAwfQ.MBd6MrGLrys168vDBaujWUlGeNUbtkwhOyd7OAE6dak" \
-H "Content-Type: application/json" \
-d '{
    "jobs": [
        {
            "description": "aaaaaa",
            "portal": "bbbbbb",
            "title": "ccccccc"
        },
        {
            "description": "aa3",
            "portal": "bb3",
            "title": "c3"
        }
    ]
}'
```

![Matching 2](https://github.com/user-attachments/assets/deffe9c5-be3d-403e-857e-3bab02429e48)


Here’s an updated version of the README section to include the new `/fail_applied` route and reflect the current version of `/applied`:

---

### User Applications

- **Get Successful Applications**:
   - `GET /applied`: Retrieves all jobs that the authenticated user successfully applied to.

- **Get Failed Applications**:
   - `GET /fail_applied`: Retrieves all jobs that the authenticated user failed to apply to.

Refer to `routers/app_router.py` for additional details on API endpoints.

#### Successful Applications (`/applied`)

Curl example:

```bash
curl -X GET "http://localhost:8006/applied" \
-H "Authorization: Bearer <your_jwt_token>" \
-H "Content-Type: application/json"
```

This endpoint retrieves all jobs that the authenticated user successfully applied to, together with the data used to apply. You only need to pass a valid token in the request header—no additional data is required.

- **Request**: 
   - Method: `GET`
   - Headers:
     - `Authorization: Bearer <your_jwt_token>`

- **Response**: 
   - A list of jobs in the `JobData` model format. The `JobData` model is defined in `/schemas` and provides the structure for each job returned by the endpoint.
   - If no successful applications are found, the endpoint returns a `404 Not Found` error with the message: "No successful applications found for this user."

---

#### Failed Applications (`/fail_applied`)

Curl example:

```bash
curl -X GET "http://localhost:8006/fail_applied" \
-H "Authorization: Bearer <your_jwt_token>" \
-H "Content-Type: application/json"
```

This endpoint retrieves all jobs that the authenticated user failed to apply to, together with the data used to apply. You only need to pass a valid token in the request header—no additional data is required.

- **Request**: 
   - Method: `GET`
   - Headers:
     - `Authorization: Bearer <your_jwt_token>`

- **Response**: 
   - A list of jobs in the `JobData` model format. The `JobData` model is defined in `/schemas` and provides the structure for each job returned by the endpoint.
   - If no failed applications are found, the endpoint returns a `404 Not Found` error with the message: "No failed applications found for this user."

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
