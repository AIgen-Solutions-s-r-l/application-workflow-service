# Build stage
FROM python:3.11-slim

LABEL org.opencontainers.image.source=https://github.com/AIHawk-Startup/application_manager_service

# Install poetry
RUN pip install poetry

# Copy poetry files
COPY pyproject.toml /app/

# Set working directory
WORKDIR /app

# Configure poetry to not create virtual environment (we're in a container)
RUN poetry config virtualenvs.create false
# Install dependencies
RUN poetry install --no-root --only main

COPY ./app /app/app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Command to run the application
CMD ["uvicorn", "app.main:app"]
