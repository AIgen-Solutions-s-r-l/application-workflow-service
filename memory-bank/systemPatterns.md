# System Patterns - Application Manager Service

This document outlines the architectural patterns, coding conventions, and design principles used in the Application Manager Service. Following these patterns ensures consistency and maintainability across the codebase.

## Architectural Patterns

### 1. Service-Oriented Architecture
- **Pattern**: Business logic is encapsulated in dedicated service classes
- **Examples**: ApplicationUploaderService, PdfResumeService, NotificationPublisher
- **Implementation**:
  - Services should have a single responsibility
  - Services should be stateless when possible
  - Dependencies should be injected or configured at initialization

### 2. Repository Pattern
- **Pattern**: Data access logic is abstracted through collections
- **Examples**: applications_collection, pdf_resumes_collection
- **Implementation**:
  - Direct database access should be limited to service classes
  - Database operations should handle errors consistently
  - Collection access should be configured in a central location (app/core/mongo.py)

### 3. Request-Response Pattern
- **Pattern**: API endpoints follow a consistent request validation and response format
- **Examples**: JobApplicationRequest model for input, JobData for responses
- **Implementation**:
  - Use Pydantic models for request validation
  - Return standardized error responses
  - Document response models with FastAPI annotations

## Coding Patterns

### 1. Asynchronous Programming
- **Pattern**: Async/await is used throughout the application
- **Examples**: All database operations and API endpoints
- **Implementation**:
  - All I/O operations should be async
  - Use proper exception handling within async functions
  - Avoid mixing sync and async code

### 2. Dependency Injection
- **Pattern**: Dependencies are injected via FastAPI's Depends
- **Examples**: current_user = Depends(get_current_user)
- **Implementation**:
  - Use for authentication, db connections, and services
  - Keep dependency functions focused and reusable
  - Document the purpose of each dependency

### 3. Error Handling
- **Pattern**: Custom exceptions with standardized handling
- **Examples**: DatabaseOperationError, handling in API endpoints
- **Implementation**:
  - Define custom exceptions in app/core/exceptions.py
  - Use try/except blocks with specific error handling
  - Log detailed errors but return appropriate user-facing messages

## Naming Conventions

1. **Files and Directories**:
   - Modules and packages: snake_case (e.g., app_router.py)
   - Test files: test_*.py (e.g., test_app_router.py)

2. **Classes and Functions**:
   - Classes: PascalCase (e.g., ApplicationUploaderService)
   - Functions and methods: snake_case (e.g., insert_application_jobs)
   - Constants: UPPER_SNAKE_CASE

3. **API Endpoints**:
   - Use descriptive names that reflect the action
   - Follow RESTful conventions when applicable
   - Include HTTP method in route handler names (e.g., get_successful_applications)

## Testing Patterns

1. **Unit Testing**:
   - Test individual components in isolation
   - Use mocking for external dependencies
   - Focus on testing business logic

2. **Integration Testing**:
   - Test interactions between components
   - Use test databases for data-related tests
   - Verify end-to-end flows

## Documentation Standards

1. **Code Documentation**:
   - Use docstrings for functions and classes
   - Follow the format shown in ApplicationUploaderService (Args, Returns, Raises)
   - Document edge cases and assumptions

2. **API Documentation**:
   - Use FastAPI's built-in documentation features
   - Include descriptions, examples, and response models
   - Document security requirements