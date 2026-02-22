#!/bin/bash

# Install dependencies
pip install -r requirements.txt

# Set a dummy database URL if not provided to avoid build failures
# Vercel builds don't need actual DB connection for static file collection
export DJANGO_SETTINGS_MODULE=api.settings

# Try to collect static files
# If DB vars are not set, use a SQLite fallback for build
if [ -z "$DB_HOST" ]; then
    echo "Database variables not set, using SQLite for static collection..."
    export DB_ENGINE=sqlite3
    export DB_NAME=":memory:"
else
    export DB_ENGINE=postgresql
fi

python manage.py collectstatic --noinput --verbosity 0 || {
    echo "Warning: Static file collection had issues, but build will continue"
}

echo "Build completed successfully"
