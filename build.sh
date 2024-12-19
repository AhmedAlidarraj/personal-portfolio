#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Create necessary directories
mkdir -p static/uploads

# Reset and initialize the database
flask db stamp head
flask db migrate -m "Remove notification system"
flask db upgrade
