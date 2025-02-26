# System Architecture - Application Manager Service

This document provides a visual representation of the Application Manager Service architecture, both current and proposed future state.

## Current System Architecture

The current architecture follows a synchronous processing model where API requests are processed immediately. Below is a diagram illustrating the current architecture:

```mermaid
graph TD
    Client[Client] -->|HTTP Request| API[FastAPI Application]
    API -->|JWT Authentication| Auth[Authentication Service]
    API -->|Store Application| MongoDB[(MongoDB)]
    API -->|Store PDF Resume| MongoDB
    API -->|Publish Notification| RabbitMQ[RabbitMQ]
    
    subgraph FastAPI Application
        AppRouter[Application Router]
        HealthRouter[Health Check Router]
        AppService[Application Uploader Service]
        ResumeService[PDF Resume Service]
        NotifyService[Notification Service]
    end
    
    AppRouter -->|Submit Jobs| AppService
    AppRouter -->|Process Resume| ResumeService
    AppService -->|Publish Notification| NotifyService
    NotifyService -->|Send Message| RabbitMQ
    
    MongoDB -->|Applications Collection| AppColl[applications_collection]
    MongoDB -->|PDF Resumes Collection| PDFColl[pdf_resumes_collection]
    MongoDB -->|Success Applications| SuccessApp[success_app]
    MongoDB -->|Failed Applications| FailedApp[failed_app]
    
    Client -->|Query Applications| API
    API -->|Return Success Apps| SuccessApp
    API -->|Return Failed Apps| FailedApp
```

## Proposed Future Architecture

The proposed architecture introduces asynchronous processing using a worker-based system, enhancing scalability and resilience:

```mermaid
graph TD
    Client[Client] -->|HTTP Request| API[FastAPI Application]
    API -->|JWT Authentication| Auth[Authentication Service]
    API -->|Store Basic Application Data| MongoDB[(MongoDB)]
    API -->|Store PDF Resume| MongoDB
    API -->|Queue Job Application| RabbitMQ[RabbitMQ]
    
    subgraph FastAPI Application
        AppRouter[Application Router]
        HealthRouter[Health Check Router]
        AppService[Application Uploader Service]
        ResumeService[PDF Resume Service]
        QueueService[Queue Service]
    end
    
    AppRouter -->|Submit Jobs| AppService
    AppRouter -->|Process Resume| ResumeService
    AppService -->|Queue Application| QueueService
    QueueService -->|Publish Message| RabbitMQ
    
    RabbitMQ -->|Consume Messages| Workers[Worker Processes]
    Workers -->|Process Applications| Workers
    Workers -->|Update Status| MongoDB
    Workers -->|Store Results| MongoDB
    
    subgraph Worker Processes
        Worker1[Worker 1]
        Worker2[Worker 2]
        WorkerN[Worker N]
    end
    
    MongoDB -->|Applications Collection| AppColl[applications_collection]
    MongoDB -->|PDF Resumes Collection| PDFColl[pdf_resumes_collection]
    MongoDB -->|Success Applications| SuccessApp[success_app]
    MongoDB -->|Failed Applications| FailedApp[failed_app]
    MongoDB -->|Application Status| StatusColl[status_collection]
    
    Client -->|Query Applications| API
    Client -->|Check Status| API
    API -->|Return Status| StatusColl
    API -->|Return Success Apps| SuccessApp
    API -->|Return Failed Apps| FailedApp
    
    subgraph Monitoring
        Prometheus[Prometheus]
        Grafana[Grafana Dashboards]
        AlertManager[Alert Manager]
    end
    
    API -->|Metrics| Prometheus
    Workers -->|Metrics| Prometheus
    RabbitMQ -->|Queue Metrics| Prometheus
    Prometheus -->|Visualize| Grafana
    Prometheus -->|Alerts| AlertManager
    AlertManager -->|Notifications| Admin[Administrator]
```

## Data Flow - Current State

1. Client submits a job application request with optional PDF resume
2. Application Router validates the request and extracts job data
3. If a PDF is included, PDF Resume Service stores it in MongoDB
4. Application Uploader Service stores the application data in MongoDB
5. Notification Service publishes a message to RabbitMQ
6. Client receives success/failure response immediately
7. The process that transitions applications between pending/success/failure states is not clearly defined in the current architecture

## Data Flow - Future State

1. Client submits a job application request with optional PDF resume
2. Application Router validates the request and extracts job data
3. If a PDF is included, PDF Resume Service stores it in MongoDB
4. Application Uploader Service creates a basic application record with "pending" status
5. Queue Service publishes the application to RabbitMQ for processing
6. Client receives acknowledgment with a tracking ID immediately
7. Worker processes consume messages from RabbitMQ
8. Workers process applications asynchronously:
   - Validate application data
   - Process resume data
   - Update application status throughout processing
   - Store final results in success_app or failed_app collections
9. Client can query the status of their application using the tracking ID
10. Monitoring system tracks the health and performance of all components

## Sequence Diagram - Application Submission (Future State)

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI Application
    participant MongoDB
    participant RabbitMQ
    participant Worker
    
    Client->>API: Submit Application + Resume
    API->>MongoDB: Store Resume
    MongoDB-->>API: Resume ID
    API->>MongoDB: Create Application Record (Pending)
    MongoDB-->>API: Application ID
    API->>RabbitMQ: Queue Application for Processing
    API-->>Client: Return Application ID + Status URL
    
    RabbitMQ->>Worker: Deliver Application Message
    Worker->>MongoDB: Update Status (Processing)
    Worker->>Worker: Process Application
    
    alt Successful Processing
        Worker->>MongoDB: Store in success_app
        Worker->>MongoDB: Update Status (Complete)
    else Failed Processing
        Worker->>MongoDB: Store in failed_app
        Worker->>MongoDB: Update Status (Failed)
        
        alt Retriable Error
            Worker->>RabbitMQ: Requeue with Backoff
        end
    end
    
    Client->>API: Check Application Status
    API->>MongoDB: Query Status
    MongoDB-->>API: Current Status
    API-->>Client: Return Status Information
```

## Component Responsibilities

### Current Components

| Component | Responsibility |
|-----------|----------------|
| Application Router | Handles API endpoints for submitting and retrieving applications |
| PDF Resume Service | Stores and retrieves PDF resumes |
| Application Uploader Service | Stores application data in MongoDB |
| Notification Service | Publishes messages to RabbitMQ |
| MongoDB | Stores application data, resumes, and results |
| RabbitMQ | Handles notification publishing |

### Future Components

| Component | Responsibility |
|-----------|----------------|
| Application Router | Handles API endpoints, initial validation |
| PDF Resume Service | Stores and retrieves PDF resumes |
| Application Uploader Service | Creates initial application records |
| Queue Service | Publishes application messages to RabbitMQ |
| Status Service | Tracks and reports application status |
| Worker Processes | Process applications asynchronously |
| MongoDB | Stores application data, resumes, results, and status |
| RabbitMQ | Message broker for application processing |
| Monitoring System | Tracks health and performance metrics |

## Scaling Considerations

The proposed architecture offers several scaling advantages:

1. **API Tier Scaling**: Since API requests return quickly, the API tier can handle more concurrent requests with fewer resources
2. **Worker Scaling**: Workers can be scaled independently based on queue depth
3. **Database Optimization**: With asynchronous processing, database operations can be optimized and batched
4. **Resilience**: Failed operations can be retried without user impact
5. **Prioritization**: Different application types can be prioritized in the queue

## Security Considerations

The architecture should maintain the following security features:

1. **Authentication**: JWT-based authentication for all client requests
2. **Authorization**: Role-based access control for administrative endpoints
3. **Data Protection**: Secure storage of resume data
4. **API Protection**: Rate limiting, input validation, and request sanitization
5. **Worker Security**: Secure communication between workers and other components