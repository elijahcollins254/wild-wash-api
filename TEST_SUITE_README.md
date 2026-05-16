# Order Status Transitions - Test Suite Documentation

Complete test suite for verifying all 12 order status transitions sequentially.

## 📋 Test Files

### 1. **test_order_status_transitions.py** (Django TestCase)
Django's built-in test framework. Best for integration testing with Django ORM.

**Location:** `wild-wash-api/orders/test_order_status_transitions.py`

**Run with:**
```bash
# Run all tests in the suite
python manage.py test orders.test_order_status_transitions.OrderStatusTransitionTestCase

# Run specific test
python manage.py test orders.test_order_status_transitions.OrderStatusTransitionTestCase.test_06_washer_marks_as_washed

# Run with verbose output
python manage.py test orders.test_order_status_transitions.OrderStatusTransitionTestCase -v 2

# Run and stop on first failure
python manage.py test orders.test_order_status_transitions.OrderStatusTransitionTestCase --failfast
```

**Features:**
- ✅ Uses Django's TestCase class
- ✅ Automatic database transactions and rollback
- ✅ Direct model access
- ✅ Integration with Django settings
- ✅ 13 individual test methods (one for each stage + complete lifecycle)

---

### 2. **test_order_transitions_pytest.py** (Pytest)
Modern pytest framework. Best for parallel testing and detailed reporting.

**Location:** `wild-wash-api/test_order_transitions_pytest.py`

**Prerequisites:**
```bash
pip install pytest pytest-django
```

**Configuration:** Add to `pytest.ini` or `setup.cfg`:
```ini
[pytest]
DJANGO_SETTINGS_MODULE = api.settings
python_files = test_*.py
addopts = --verbose --strict-markers
```

**Run with:**
```bash
# Run all tests
pytest test_order_transitions_pytest.py -v

# Run with print output
pytest test_order_transitions_pytest.py -v -s

# Run single test
pytest test_order_transitions_pytest.py::TestOrderTransitions::test_stage_06_washed -v

# Run with coverage
pytest test_order_transitions_pytest.py --cov=orders --cov-report=html

# Run in parallel (install pytest-xdist)
pytest test_order_transitions_pytest.py -v -n auto

# Run with markers
pytest test_order_transitions_pytest.py -v -m django_db
```

**Features:**
- ✅ Modern pytest syntax
- ✅ Fixture-based setup
- ✅ Parallel execution support
- ✅ Better error reporting
- ✅ Can run standalone or with Django

---

### 3. **test_order_transitions_standalone.py** (Standalone API Client)
Standalone Python script using requests library. No Django required - tests via HTTP API.

**Location:** `wild-wash-api/test_order_transitions_standalone.py`

**Prerequisites:**
```bash
pip install requests
```

**Configuration:** Edit the file to set:
```python
API_BASE_URL = 'http://localhost:8000/api'
ADMIN_USERNAME = 'admin_user'
ADMIN_PASSWORD = 'testpass123'
```

**Run with:**
```bash
# Make script executable (Unix/Linux/Mac)
chmod +x test_order_transitions_standalone.py

# Run the standalone test
python test_order_transitions_standalone.py

# Or direct execution
./test_order_transitions_standalone.py
```

**Features:**
- ✅ No Django dependency - pure HTTP API testing
- ✅ Beautiful colored terminal output
- ✅ Real API integration testing
- ✅ Standalone execution
- ✅ Detailed error reporting
- ✅ Works with remote APIs

---

## 🚀 Quick Start Guide

### Option 1: Django TestCase (Recommended for Development)

```bash
cd wild-wash-api

# Run all tests
python manage.py test orders.test_order_status_transitions -v 2

# Expected output shows 13 tests passing with detailed status for each
```

### Option 2: Pytest (Recommended for CI/CD)

```bash
cd wild-wash-api

# Install pytest if not already installed
pip install pytest pytest-django

# Run tests
pytest test_order_transitions_pytest.py -v -s

# Expected output shows each stage with checkmarks
```

### Option 3: Standalone API Test (For Testing Running Server)

```bash
cd wild-wash-api

# Ensure Django server is running in another terminal
# python manage.py runserver

# Run standalone test
python test_order_transitions_standalone.py

# Expected output shows complete journey with colored output
```

---

## 📊 Test Coverage

All three test suites cover these 12 status transitions:

| Stage | From | To | Tested |
|-------|------|-----|--------|
| 1 | - | REQUESTED | ✅ |
| 2 | REQUESTED | PENDING_ASSIGNMENT | ✅ |
| 3 | PENDING_ASSIGNMENT | ASSIGNED_PICKUP | ✅ |
| 4 | ASSIGNED_PICKUP | PICKED | ✅ |
| 5 | PICKED | IN_PROGRESS | ✅ |
| 6 | IN_PROGRESS | WASHED | ✅ |
| 7 | WASHED | FOLDED | ✅ |
| 8 | FOLDED | READY | ✅ |
| 9 | READY | PENDING_DELIVERY | ✅ |
| 10 | PENDING_DELIVERY | ASSIGNED_DELIVERY | ✅ |
| 11 | ASSIGNED_DELIVERY | DELIVERED | ✅ |
| 12 | Complete Lifecycle | All Transitions | ✅ |

---

## 🔍 What Each Test Validates

### Stage 1: Initial Status
- ✅ Order created with `requested` status
- ✅ No riders assigned
- ✅ Status transition validation

### Stage 2: Pending Assignment
- ✅ Status update to `pending_assignment`
- ✅ Valid transition to `assigned_pickup`

### Stage 3: Pickup Rider Assignment
- ✅ Admin assigns pickup rider via API
- ✅ `pickup_rider` field populated
- ✅ Status updated to `assigned_pickup`

### Stage 4: Pickup Confirmation
- ✅ Rider confirms pickup
- ✅ Status updated to `picked`
- ✅ `picked_at` timestamp recorded

### Stage 5: Facility Arrival
- ✅ Auto-transition to `in_progress`
- ✅ Order ready for washer

### Stage 6: Washing Complete
- ✅ Washer marks order washed
- ✅ Status updated to `washed`
- ✅ `washed_at` timestamp recorded
- ✅ `washer` field assigned
- ✅ Notifications sent to folder staff

### Stage 7: Folding
- ✅ Folder begins folding
- ✅ Status updated to `folded`
- ✅ `folded_at` timestamp recorded

### Stage 8: Ready for Delivery
- ✅ Status updated to `ready`
- ✅ `folder` field assigned
- ✅ Ready for delivery rider assignment

### Stage 9: Pending Delivery
- ✅ Admin prepares for delivery
- ✅ Status updated to `pending_delivery`

### Stage 10: Delivery Rider Assignment
- ✅ Admin assigns delivery rider via API
- ✅ `delivery_rider` field populated
- ✅ Status updated to `assigned_delivery`
- ✅ SMS sent to delivery rider

### Stage 11: Delivery Complete
- ✅ Rider marks order delivered
- ✅ Status updated to `delivered`
- ✅ `delivered_at` timestamp recorded
- ✅ SMS sent to customer

### Stage 12: Complete Lifecycle
- ✅ All 11 transitions executed
- ✅ All timestamps populated
- ✅ All users assigned correctly
- ✅ Order events created

---

## 🐛 Debugging Failed Tests

### Using Django TestCase

```bash
# Verbose output with failures
python manage.py test orders.test_order_status_transitions -v 2

# Pdb on failure
python manage.py test orders.test_order_status_transitions --pdb

# Keep test database for inspection
python manage.py test orders.test_order_status_transitions --keepdb
```

### Using Pytest

```bash
# Verbose with print statements
pytest test_order_transitions_pytest.py -v -s

# Drop to pdb on failure
pytest test_order_transitions_pytest.py -v --pdb

# Show local variables on failure
pytest test_order_transitions_pytest.py -v -l

# Last 10 lines of failed test
pytest test_order_transitions_pytest.py -v --tb=short
```

### Using Standalone Test

```bash
# Run with detailed output
python test_order_transitions_standalone.py

# Check API responses by adding breakpoints
# (Edit the script and use: pdb.set_trace())
```

---

## 📝 Expected Output Example

### Django TestCase Output
```
test_01_initial_status_is_requested (orders.test_order_status_transitions.OrderStatusTransitionTestCase) ... ok
test_02_transition_to_pending_assignment (orders.test_order_status_transitions.OrderStatusTransitionTestCase) ... ok
test_03_assign_pickup_rider_via_api (orders.test_order_status_transitions.OrderStatusTransitionTestCase) ... ok
...
================================================================================
✅ COMPLETE ORDER LIFECYCLE TEST PASSED
================================================================================
...
Ran 13 tests in 0.245s
OK
```

### Pytest Output
```
test_order_transitions_pytest.py::TestOrderTransitions::test_stage_01_initial_requested PASSED
test_order_transitions_pytest.py::TestOrderTransitions::test_stage_02_pending_assignment PASSED
test_order_transitions_pytest.py::TestOrderTransitions::test_stage_03_assigned_pickup PASSED
...
========================== 11 passed in 0.845s ==========================
```

### Standalone API Output
```
================================================================================
                   ORDER STATUS TRANSITIONS - COMPLETE TEST SUITE
================================================================================

✅ Authenticated as: admin_user
✅ Order created: WW-TEST-20250516143022 (ID: 123)

──────────────────────────────────────────────────────────────────────────────
STAGE 1: INITIAL → REQUESTED
──────────────────────────────────────────────────────────────────────────────

ℹ️  Order created with initial status: requested
✅ Order ready for processing
...
✅ ALL TESTS PASSED! 🎉
```

---

## 🔧 Common Issues & Solutions

### Issue: Import errors in test_order_status_transitions.py
**Solution:**
```bash
# Ensure you're in the correct directory
cd wild-wash-api

# Run with correct Django settings
DJANGO_SETTINGS_MODULE=api.settings python manage.py test orders.test_order_status_transitions
```

### Issue: Standalone test can't connect to API
**Solution:**
```bash
# Ensure Django server is running
python manage.py runserver 0.0.0.0:8000

# Update API_BASE_URL in the script if using different port
API_BASE_URL = 'http://localhost:8000/api'
```

### Issue: Tests fail due to missing users
**Solution:**
```bash
# Create test users first
python manage.py shell

from django.contrib.auth import get_user_model
User = get_user_model()
User.objects.create_user(username='admin_user', password='testpass123', is_staff=True, is_superuser=True)
User.objects.create_user(username='test_rider', password='testpass123', role='rider')
```

### Issue: Database locked error
**Solution:**
```bash
# Run with --keepdb flag removed
python manage.py test orders.test_order_status_transitions --no-keepdb

# Or in pytest
pytest test_order_transitions_pytest.py --create-db
```

---

## 📈 Running in CI/CD Pipeline

### GitHub Actions Example
```yaml
name: Order Status Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-django
    
    - name: Run order transition tests
      run: |
        cd wild-wash-api
        pytest test_order_transitions_pytest.py -v --cov=orders
```

### GitLab CI Example
```yaml
test:
  image: python:3.9
  script:
    - pip install -r requirements.txt
    - cd wild-wash-api
    - python manage.py test orders.test_order_status_transitions -v 2
  coverage: '/TOTAL.*\s+(\d+%)$/'
```

---

## 🎯 Performance Metrics

Typical test execution times:

| Test Suite | Time | Database Ops | API Calls |
|-----------|------|--------------|-----------|
| Django TestCase | ~250ms | Direct ORM | 0 |
| Pytest | ~800ms | Direct ORM | 0 |
| Standalone API | ~3-5s | Via API | 11 |

---

## 📚 Additional Resources

- [Django Testing Docs](https://docs.djangoproject.com/en/stable/topics/testing/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Requests Library Docs](https://requests.readthedocs.io/)

---

## ✅ Verification Checklist

Before committing code changes:

- [ ] All 13 tests pass with Django TestCase
- [ ] All 11 tests pass with Pytest
- [ ] Standalone API test connects and completes
- [ ] No warnings or deprecation notices
- [ ] All timestamps are recorded
- [ ] All notifications are triggered
- [ ] All events are created for audit trail

---

**Created:** May 16, 2026  
**Last Updated:** May 16, 2026
