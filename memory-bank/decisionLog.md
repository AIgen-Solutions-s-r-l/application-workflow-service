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