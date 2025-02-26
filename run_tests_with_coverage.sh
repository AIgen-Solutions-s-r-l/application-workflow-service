#!/bin/bash

# Run tests with coverage reporting
python -m pytest --cov=app --cov-report=term-missing --cov-report=html tests/