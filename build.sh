#!/bin/bash

# Install dependencies
pip install -r requirements.txt

# Collect Django static files
python manage.py collectstatic --noinput

echo "Build script completed successfully"
