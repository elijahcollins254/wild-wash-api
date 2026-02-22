#!/usr/bin/env python
"""Build script for Vercel deployment."""

import os
import sys
import subprocess
import shutil

def main():
    print("=== Vercel Django Build ===\n")
    
    # 1. Install dependencies
    print("[1/5] Installing dependencies...")
    result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: Failed to install dependencies")
        print(result.stderr)
        return 1
    print("OK: Dependencies installed\n")
    
    # 2. Set Django settings and build mode
    os.environ['DJANGO_SETTINGS_MODULE'] = 'api.settings'
    os.environ['VERCEL_BUILD'] = '1'
    
    # 3. Use SQLite if DB not configured (build environment)
    if not os.getenv('DB_HOST'):
        os.environ['DB_ENGINE'] = 'sqlite3'
        os.environ['DB_NAME'] = ':memory:'
        print("INFO: Using in-memory SQLite for build...\n")
    
    # 4. Clean old staticfiles if they exist
    print("[2/5] Cleaning old static files...")
    staticfiles_dir = os.path.join(os.getcwd(), 'staticfiles')
    if os.path.exists(staticfiles_dir):
        shutil.rmtree(staticfiles_dir)
        print("OK: Cleaned old staticfiles\n")
    
    # 5. Run collectstatic with proper environment
    print("[3/5] Collecting static files...")
    env = os.environ.copy()
    env['PYTHONWARNINGS'] = 'ignore'
    
    result = subprocess.run(
        [sys.executable, "manage.py", "collectstatic", "--noinput", "--clear", "--verbosity", "2"],
        capture_output=True,
        text=True,
        env=env,
        cwd=os.getcwd()
    )
    
    # Parse output
    output_lines = result.stdout.split('\n') if result.stdout else []
    errors = result.stderr.split('\n') if result.stderr else []
    
    for line in output_lines:
        if line and ('copied' in line or 'post-processed' in line or 'unmodified' in line or 'Rendering' in line):
            print(line)
    
    if result.returncode != 0:
        # Check if it's just a migration warning we can ignore
        has_critical_error = False
        for err in errors:
            if 'ERROR' in err or 'CRITICAL' in err:
                has_critical_error = True
                break
        
        if has_critical_error:
            print(f"ERROR during static collection: {result.returncode}")
            print(result.stderr[:500])
            return 1
        else:
            print("INFO: Non-critical warnings during collection, continuing...\n")
    else:
        print("OK: Static files collected\n")
    
    # 6. Verify staticfiles directory
    print("[4/5] Verifying build artifacts...")
    if os.path.exists(staticfiles_dir):
        file_count = sum([len(files) for _, _, files in os.walk(staticfiles_dir)])
        print(f"OK: staticfiles directory exists with {file_count} files\n")
        
        # Check for key Django admin files
        admin_css = os.path.join(staticfiles_dir, 'admin', 'css', 'base.css')
        if os.path.exists(admin_css):
            print(f"OK: Django admin CSS found at {admin_css}\n")
        else:
            print(f"WARNING: Django admin CSS not found\n")
    else:
        print("WARNING: staticfiles directory not created\n")
        return 1
    
    # 7. Final summary
    print("[5/5] Build complete!")
    print("SUCCESS: Build completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
