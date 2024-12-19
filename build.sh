#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Create necessary directories
mkdir -p static/uploads

# Initialize and upgrade the database
export FLASK_APP=app.py
flask db stamp head
flask db migrate -m "Add notification fields"
flask db upgrade
