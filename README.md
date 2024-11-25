
# Application Manager Service

The **Application Manager Service** is a Python-based backend service designed to manage application workflows and handle user resumes and job tracking. It integrates with RabbitMQ for asynchronous message processing and MongoDB/PostgreSQL for data storage.

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
- RabbitMQ server
- MongoDB server
- PostgreSQL server
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
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
SERVICE_NAME=application_manager_service
MONGO_URI=mongodb://localhost:27017/
POSTGRES_URI=postgresql://user:password@localhost:5432/database
```

### Database Setup

Run the database initialization scripts to set up MongoDB and PostgreSQL:

- Use `init_db.py` for seeding MongoDB.
- Ensure PostgreSQL is configured with the provided URI.

---

## Application Workflow

1. **RabbitMQ Messaging**:
   - Publishes messages to RabbitMQ queues for asynchronous processing.

2. **Database Management**:
   - Stores user and job data in MongoDB.
   - Utilizes PostgreSQL for relational data management.

3. **Resume Processing**:
   - Processes and validates resumes using the logic in `resume_ops.py`.

4. **API Interaction**:
   - Provides endpoints for managing resumes, jobs, and user data.

---

## Running the Application

Run the application using the following command:

```bash
python app/main.py
```

Ensure RabbitMQ, MongoDB, and PostgreSQL servers are running and accessible.

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
│   ├── services/           # Business logic and messaging handlers
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

- **User Operations**:
   - `GET /users`: Fetch all users.
   - `POST /users`: Create a new user.
- **Job Operations**:
   - `GET /jobs`: Fetch all jobs.
   - `POST /jobs`: Create a new job.
- **Resume Operations**:
   - `POST /resumes`: Process and store a resume.

Refer to `routers/app_router.py` for additional details on API endpoints.

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

---
