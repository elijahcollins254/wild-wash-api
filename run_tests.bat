@echo off
REM Quick reference: Run all test suites for Windows

setlocal enabledelayedexpansion

echo.
echo ╔════════════════════════════════════════════════════════════════════════════╗
echo ║           Order Status Transitions - Test Suite Quick Start               ║
echo ╚════════════════════════════════════════════════════════════════════════════╝
echo.

cd wild-wash-api

echo ┌─ Option 1: Django TestCase (Recommended for Development) ─────────────────┐
echo │ Run: python manage.py test orders.test_order_status_transitions -v 2     │
echo │ Time: ~250ms                                                              │
echo │ Output: Clean test summary with all 13 tests                              │
echo └─────────────────────────────────────────────────────────────────────────────┘
echo.
set /p response="Run Django Tests? (y/n): "
if /i "%response%"=="y" (
    echo.
    echo Running Django tests...
    python manage.py test orders.test_order_status_transitions -v 2
    echo.
)

echo.
echo ┌─ Option 2: Pytest (Recommended for CI/CD) ────────────────────────────────┐
echo │ Run: pytest test_order_transitions_pytest.py -v -s                        │
echo │ Time: ~800ms                                                              │
echo │ Output: Detailed stage-by-stage progress with colored output              │
echo │ Prerequisites: pip install pytest pytest-django                           │
echo └─────────────────────────────────────────────────────────────────────────────┘
echo.
set /p response="Run Pytest? (y/n): "
if /i "%response%"=="y" (
    echo.
    echo Checking pytest installation...
    pip list | findstr /I "pytest" >nul
    if errorlevel 1 (
        echo Installing pytest...
        pip install pytest pytest-django
    )
    echo.
    echo Running pytest tests...
    pytest test_order_transitions_pytest.py -v -s
    echo.
)

echo.
echo ┌─ Option 3: Standalone API Test (For Testing Running Server) ──────────────┐
echo │ Prerequisites: pip install requests                                       │
echo │                - Django server running: python manage.py runserver       │
echo │ Run: python test_order_transitions_standalone.py                          │
echo │ Time: ~3-5 seconds                                                        │
echo │ Output: Colored terminal output with complete journey                     │
echo └─────────────────────────────────────────────────────────────────────────────┘
echo.
set /p response="Run Standalone Test? (y/n): "
if /i "%response%"=="y" (
    echo.
    echo Checking requests installation...
    pip list | findstr /I "requests" >nul
    if errorlevel 1 (
        echo Installing requests...
        pip install requests
    )
    echo.
    echo Ensure Django server is running: python manage.py runserver
    echo.
    pause
    echo.
    echo Running standalone tests...
    python test_order_transitions_standalone.py
    echo.
)

echo.
echo ╔════════════════════════════════════════════════════════════════════════════╗
echo ║                            Test Complete                                   ║
echo ╚════════════════════════════════════════════════════════════════════════════╝
echo.
