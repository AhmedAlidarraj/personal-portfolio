#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Create necessary directories
mkdir -p static/uploads

# Initialize and upgrade the database
flask db init || true
flask db migrate -m "Initial migration" || true
flask db upgrade || true
