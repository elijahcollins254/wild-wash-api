#!/bin/bash
# Quick reference: Run all test suites

echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║           Order Status Transitions - Test Suite Quick Start               ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

cd wild-wash-api

echo "┌─ Option 1: Django TestCase (Recommended for Development) ─────────────────┐"
echo "│ Run: python manage.py test orders.test_order_status_transitions -v 2     │"
echo "│ Time: ~250ms                                                              │"
echo "│ Output: Clean test summary with all 13 tests                              │"
echo "└─────────────────────────────────────────────────────────────────────────────┘"
echo ""
echo "Run Django Tests? (y/n): "
read response
if [ "$response" = "y" ]; then
    echo ""
    echo "Running Django tests..."
    python manage.py test orders.test_order_status_transitions -v 2
    echo ""
fi

echo ""
echo "┌─ Option 2: Pytest (Recommended for CI/CD) ────────────────────────────────┐"
echo "│ Run: pytest test_order_transitions_pytest.py -v -s                        │"
echo "│ Time: ~800ms                                                              │"
echo "│ Output: Detailed stage-by-stage progress with colored output              │"
echo "│ Prerequisites: pip install pytest pytest-django                           │"
echo "└─────────────────────────────────────────────────────────────────────────────┘"
echo ""
echo "Run Pytest? (y/n): "
read response
if [ "$response" = "y" ]; then
    echo ""
    echo "Checking pytest installation..."
    python -m pip list | grep pytest > /dev/null
    if [ $? -ne 0 ]; then
        echo "Installing pytest..."
        pip install pytest pytest-django
    fi
    echo ""
    echo "Running pytest tests..."
    pytest test_order_transitions_pytest.py -v -s
    echo ""
fi

echo ""
echo "┌─ Option 3: Standalone API Test (For Testing Running Server) ──────────────┐"
echo "│ Prerequisites: pip install requests                                       │"
echo "│                - Django server running: python manage.py runserver       │"
echo "│ Run: python test_order_transitions_standalone.py                          │"
echo "│ Time: ~3-5 seconds                                                        │"
echo "│ Output: Colored terminal output with complete journey                     │"
echo "└─────────────────────────────────────────────────────────────────────────────┘"
echo ""
echo "Run Standalone Test? (y/n): "
read response
if [ "$response" = "y" ]; then
    echo ""
    echo "Checking requests installation..."
    python -m pip list | grep requests > /dev/null
    if [ $? -ne 0 ]; then
        echo "Installing requests..."
        pip install requests
    fi
    echo ""
    echo "Ensure Django server is running (python manage.py runserver)"
    echo "Press ENTER to continue..."
    read
    echo ""
    echo "Running standalone tests..."
    python test_order_transitions_standalone.py
    echo ""
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║                            Test Complete                                   ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
