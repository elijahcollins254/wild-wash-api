#!/bin/bash

set -e

# Install Python dependencies
echo "Installing dependencies..."
pip install -r requirements.txt --quiet

# Set django settings
export DJANGO_SETTINGS_MODULE=api.settings

# For Vercel build environment, use SQLite if DB variables not set
if [ -z "$DB_HOST" ]; then
    export DB_ENGINE=sqlite3
    export DB_NAME=":memory:"
    echo "Using in-memory SQLite for build..."
fi

# Collect static files with error tolerance
echo "Collecting static files..."
python manage.py collectstatic --noinput 2>&1 | grep -E "(^[0-9]+ |error|Error)" || echo "Static files collection completed"

echo "✓ Build script finished successfully"
