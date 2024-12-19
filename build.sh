#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Create upload directory
mkdir -p static/uploads

# Initialize the database
python3 -c "from app import db; db.create_all()"
