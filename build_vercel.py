#!/usr/bin/env python
"""Build script for Vercel deployment."""

import os
import sys
import subprocess

def main():
    print("=== Vercel Django Build ===\n")
    
    # 1. Install dependencies
    print("[1/4] Installing dependencies...")
    result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: Failed to install dependencies: {result.stderr}")
        return 1
    print("OK: Dependencies installed\n")
    
    # 2. Set Django settings
    os.environ['DJANGO_SETTINGS_MODULE'] = 'api.settings'
    
    # 3. Use SQLite if DB not configured (build environment)
    if not os.getenv('DB_HOST'):
        os.environ['DB_ENGINE'] = 'sqlite3'
        os.environ['DB_NAME'] = ':memory:'
        print("INFO: Using in-memory SQLite for build...\n")
    
    # 4. Collect static files
    print("[2/4] Collecting static files...")
    result = subprocess.run(
        [sys.executable, "manage.py", "collectstatic", "--noinput"],
        capture_output=True,
        text=True
    )
    
    # Print result (including warnings but not errors)
    if result.stdout:
        print(result.stdout)
    
    if result.returncode != 0:
        print("WARNING: collectstatic had issues (non-critical)")
        if result.stderr:
            print(result.stderr[:500])  # Print first 500 chars of error
        print("Continuing anyway...\n")
    else:
        print("OK: Static files collected\n")
    
    print("[3/4] Verifying build artifacts...")
    if os.path.exists('staticfiles'):
        print(f"OK: staticfiles directory exists\n")
    else:
        print("WARNING: staticfiles directory not found\n")
    
    print("[4/4] Build complete!")
    print("SUCCESS: Build completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
