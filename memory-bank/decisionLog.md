# Decision Log - Application Manager Service

This document tracks key architectural and design decisions made during the development of the Application Manager Service.

## February 27, 2025 - Initial Architecture Review

**Context:** Initial review of the Application Manager Service codebase to understand architectural decisions.

**Observations:**

1. **FastAPI Framework**
   - **Decision:** The service uses FastAPI as the web framework.
   - **Rationale:** FastAPI provides high performance, automatic OpenAPI documentation, and modern Python features (type hints, async support).
   - **Implications:** Facilitates robust API development with built-in validation and documentation.

2. **MongoDB Database**
   - **Decision:** MongoDB is used as the primary database.
   - **Rationale:** Document-oriented database fits well with the varying structure of job applications and resumes.
   - **Implications:** Provides flexibility for storing different types of application data but requires careful management of schema evolution.

3. **Service-Based Architecture**
   - **Decision:** Code is organized into specialized services (ApplicationUploaderService, PdfResumeService, NotificationService).
   - **Rationale:** Separation of concerns improves maintainability and allows for isolated testing.
   - **Implications:** Services can evolve independently, but need clear interface contracts.

4. **JWT Authentication**
   - **Decision:** JWT-based authentication is implemented.
   - **Rationale:** Industry standard for stateless authentication in web services.
   - **Implications:** Provides secure access to resources but requires proper key management and token validation.

5. **RabbitMQ for Notifications**
   - **Decision:** RabbitMQ is used for notification services.
   - **Rationale:** Enables asynchronous communication and decouples the application submission from notification delivery.
   - **Implications:** Improves scalability but introduces operational complexity for managing the message broker.

**Notes for Future Decisions:**
- Consider how to improve error handling and recovery mechanisms
- Evaluate the current application processing workflow for optimization opportunities
- Assess the potential need for caching frequently accessed application data

## February 27, 2025 - Testing Strategy Decision

**Context:** The Application Manager Service lacks comprehensive test coverage, making it difficult to ensure reliability and stability, especially when implementing new features or architectural changes. A robust testing strategy is needed to support ongoing development.

**Decision:**

1. **Comprehensive Test Suite Approach**
   - **Decision:** Implement a multi-layered testing approach with unit, integration, and end-to-end tests.
   - **Rationale:** Different test types are needed to ensure both component-level correctness and system-wide functionality.
   - **Implications:** Requires more initial development time but provides long-term stability and confidence in changes.

## February 27, 2025 - JobData Schema Modification

**Context:** The `JobData` model in `app/models/job.py` had its `id` field defined as `Optional[UUID]` type, which was causing issues.

**Decision:**
- **Change:** Modified the `id` field in `JobData` model from `Optional[UUID]` to `Optional[str]`.
- **Rationale:** String IDs offer more flexibility and are more commonly used across various systems and databases. They can accommodate both UUID strings and other ID formats without requiring type conversion.
- **Implementation:** Removed the `uuid` import and changed the field type definition. All tests were run to verify the change didn't break existing functionality.
- **Implications:**
  - More flexible ID handling
  - Better compatibility with external systems that might use different ID formats
  - Simplified data handling as string manipulation is more straightforward than UUID operations

2. **70% Minimum Coverage Target**
   - **Decision:** Set a minimum code coverage target of 70% for critical components.
   - **Rationale:** Balances reasonable test coverage with development effort, focusing on the most important functionality.
   - **Implications:** Some edge cases may remain untested, but critical paths will be verified.

3. **Mock-Based Testing for External Dependencies**
   - **Decision:** Use mocking for MongoDB, RabbitMQ, and other external dependencies in unit tests.
   - **Rationale:** Enables faster, more reliable tests that focus on application logic rather than external system behavior.
   - **Implications:** Requires careful design of mocks to accurately represent external system behavior.

4. **Prioritization of Service Layer Testing**
   - **Decision:** Prioritize testing core services (ApplicationUploaderService, PdfResumeService, NotificationPublisher, AsyncRabbitMQClient).
   - **Rationale:** These components contain the critical business logic and integration points.
   - **Implications:** Focuses testing efforts on the most complex and critical parts of the system.

5. **Pytest + pytest-asyncio Framework**
   - **Decision:** Use pytest with pytest-asyncio for testing async functions.
   - **Rationale:** Best supports testing of asynchronous code patterns used throughout the application.
   - **Implications:** Standardizes testing approach and takes advantage of pytest's extensive ecosystem.

**Implementation Approach:**
- Develop incremental testing strategy starting with core services and expanding outward
- Create test fixtures for common dependencies and test data
- Use coverage reports to identify gaps and guide further test development