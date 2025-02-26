# Application Manager Service - Product Context

## Project Overview
The Application Manager Service is a Python-based backend service designed to manage job application workflows, handle user resumes, and track job applications. It interacts with MongoDB for data storage and uses FastAPI for API-based interactions.

## Key Features
1. **Managing User Applications**: Handles user data and application workflows
2. **Resume Processing**: Validates and stores resumes for job applications  
3. **Job Application Tracking**: Tracks the progress of applications, categorizing them as successful or failed

## Technical Stack
- **Backend**: Python 3.12.3 with FastAPI
- **Database**: MongoDB
- **Message Broker**: RabbitMQ (for notifications)
- **Authentication**: JWT-based authentication system

## System Components
1. **API Layer**: FastAPI endpoints for application submission and retrieval
2. **Service Layer**: Business logic for processing applications and resumes
3. **Data Layer**: MongoDB collections for storing applications, resumes, and job data
4. **Notification System**: RabbitMQ-based notification for application status updates

## Data Models
- **JobData**: Represents job details including title, description, company, location, etc.
- **JobApplicationRequest**: Request model for receiving job application data
- **DetailedJobData**: Model for detailed job information including resume and cover letter

## Collections in MongoDB
- **applications_collection**: Stores pending job applications
- **pdf_resumes_collection**: Stores uploaded PDF resumes
- **success_app**: Stores successful job applications
- **failed_app**: Stores failed job applications

## API Endpoints
- **POST /applications**: Submit jobs and save application data
- **GET /applied**: Get all successful applications for the authenticated user
- **GET /applied/{app_id}**: Get detailed information for a specific successful application
- **GET /fail_applied**: Get all failed applications for the authenticated user
- **GET /fail_applied/{app_id}**: Get detailed information for a specific failed application

## Memory Bank Structure
This Memory Bank contains the following core files:
- **productContext.md**: This file - Project overview, goals, and technical details
- **activeContext.md**: Current session state and goals
- **progress.md**: Work completed and next steps
- **decisionLog.md**: Key architectural decisions and their rationale

Additional files may be created as needed to document specific aspects of the system.