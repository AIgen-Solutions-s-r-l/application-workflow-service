# Application Manager Service Test Suite

This directory contains a comprehensive test suite for the Application Manager Service, designed to achieve at least 70% code coverage for critical components.

## Test Structure

The test suite is organized as follows:

- `conftest.py`: Contains shared fixtures and mocks for tests
- `services/`: Tests for service classes
  - `test_application_uploader_service.py`: Tests for ApplicationUploaderService
  - `test_pdf_resume_service.py`: Tests for PdfResumeService
  - `test_notification_service.py`: Tests for NotificationPublisher
- `core/`: Tests for core functionality
  - `test_rabbitmq_client.py`: Tests for AsyncRabbitMQClient
- `routers/`: Tests for API endpoints
  - `test_app_router_helpers.py`: Tests for router helper functions
  - `test_app_router_submit.py`: Tests for application submission endpoints
  - `test_app_router_retrieve.py`: Tests for application retrieval endpoints
- `integration/`: Integration tests for complete workflows
  - `test_application_flow.py`: End-to-end tests for application submission and retrieval

## Running the Tests

### Prerequisites

Make sure you have all dependencies installed:

```bash
poetry install
```

### Running All Tests

To run the entire test suite:

```bash
pytest
```

### Running Tests with Coverage

To run the tests with coverage reporting:

```bash
./run_tests_with_coverage.sh
```

Or manually:

```bash
python -m pytest --cov=app --cov-report=term-missing --cov-report=html tests/
```

This will generate:
1. A terminal report showing which lines are not covered
2. An HTML report in the `htmlcov/` directory

### Running Specific Test Files or Groups

To run specific tests:

```bash
# Run a specific test file
pytest tests/services/test_application_uploader_service.py

# Run tests matching a pattern
pytest -k "application_uploader"

# Run tests in a specific directory
pytest tests/services/
```

## Coverage Goals

The goal is to achieve at least 70% code coverage for critical components:

- Service Layer: ApplicationUploaderService, PdfResumeService, NotificationPublisher
- Core Components: AsyncRabbitMQClient, MongoDB interactions
- API Endpoints: Application submission and retrieval

## Adding New Tests

When adding new tests:

1. Follow the existing structure
2. Use fixtures from `conftest.py` where appropriate
3. Add test cases for both success and error paths
4. Mock external dependencies (MongoDB, RabbitMQ)
5. Run the tests with coverage to identify gaps