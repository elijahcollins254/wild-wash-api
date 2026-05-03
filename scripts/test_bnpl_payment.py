#!/usr/bin/env python
"""
Test script for BNPL balance payment functionality.
Tests the M-Pesa query, payment initiation, and balance tracking.
"""

import os
import sys
import django
import requests
import logging
from decimal import Decimal
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')
django.setup()

from django.contrib.auth.models import User
from payments.models import BNPLUser, Payment
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_test_user():
    """Create a test user with BNPL enrollment."""
    username = f'bnpl_test_{datetime.now().timestamp()}'
    user = User.objects.create_user(
        username=username,
        email=f'{username}@test.com',
        password='testpass123'
    )
    
    # Create token
    token, _ = Token.objects.get_or_create(user=user)
    
    # Create BNPL user
    bnpl_user = BNPLUser.objects.create(
        user=user,
        phone_number='254712345678',
        credit_limit=Decimal('5000.00'),
        current_balance=Decimal('2500.00'),
        is_active=True
    )
    
    logger.info(f"✓ Created test user: {username}")
    logger.info(f"✓ BNPL Balance: KES {bnpl_user.current_balance}")
    logger.info(f"✓ Credit Limit: KES {bnpl_user.credit_limit}")
    logger.info(f"✓ Token: {token.key}")
    
    return user, token, bnpl_user


def test_get_bnpl_status(client, token):
    """Test getting BNPL status endpoint."""
    logger.info("\n=== Testing GET /payments/bnpl/status/ ===")
    
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    response = client.get('/api/payments/bnpl/status/')
    
    logger.info(f"Status Code: {response.status_code}")
    logger.info(f"Response: {response.json()}")
    
    if response.status_code == 200:
        data = response.json()
        logger.info(f"✓ BNPL Status Retrieved:")
        logger.info(f"  - Is Enrolled: {data.get('is_enrolled')}")
        logger.info(f"  - Current Balance: KES {data.get('current_balance')}")
        logger.info(f"  - Credit Limit: KES {data.get('credit_limit')}")
        logger.info(f"  - Is Active: {data.get('is_active')}")
        return data
    else:
        logger.error(f"✗ Failed to get BNPL status: {response.json()}")
        return None


def test_check_pending_payment(client, token):
    """Test checking pending payments."""
    logger.info("\n=== Testing GET /payments/bnpl/check_pending_payment/ ===")
    
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    response = client.get('/api/payments/bnpl/check_pending_payment/')
    
    logger.info(f"Status Code: {response.status_code}")
    logger.info(f"Response: {response.json()}")
    
    if response.status_code == 200:
        data = response.json()
        logger.info(f"✓ Pending Payment Check:")
        logger.info(f"  - Has Pending: {data.get('has_pending_payment')}")
        logger.info(f"  - Status: {data.get('payment_status')}")
        logger.info(f"  - Message: {data.get('message')}")
        return data
    else:
        logger.error(f"✗ Failed to check pending payment: {response.json()}")
        return None


def test_pay_full_balance(client, token, bnpl_user):
    """Test paying full BNPL balance."""
    logger.info("\n=== Testing POST /payments/bnpl/pay_balance/ (Full Balance) ===")
    
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    
    payload = {
        'phone_number': bnpl_user.phone_number
    }
    
    logger.info(f"Payload: {payload}")
    logger.info(f"Balance to pay: KES {bnpl_user.current_balance}")
    
    response = client.post(
        '/api/payments/bnpl/pay_balance/',
        data=payload,
        format='json'
    )
    
    logger.info(f"Status Code: {response.status_code}")
    logger.info(f"Response: {response.json()}")
    
    if response.status_code == 200:
        data = response.json()
        logger.info(f"✓ Payment Initiated:")
        logger.info(f"  - Amount: KES {data.get('amount')}")
        logger.info(f"  - CheckoutRequestID: {data.get('checkout_request_id')}")
        logger.info(f"  - Message: {data.get('message')}")
        return data
    else:
        logger.error(f"✗ Failed to initiate payment: {response.json()}")
        return None


def test_pay_custom_amount(client, token, bnpl_user):
    """Test paying custom BNPL amount."""
    logger.info("\n=== Testing POST /payments/bnpl/pay_balance/ (Custom Amount) ===")
    
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    
    custom_amount = float(bnpl_user.current_balance) / 2  # Pay half
    
    payload = {
        'phone_number': bnpl_user.phone_number,
        'amount': custom_amount
    }
    
    logger.info(f"Payload: {payload}")
    logger.info(f"Amount to pay: KES {custom_amount}")
    
    response = client.post(
        '/api/payments/bnpl/pay_balance/',
        data=payload,
        format='json'
    )
    
    logger.info(f"Status Code: {response.status_code}")
    logger.info(f"Response: {response.json()}")
    
    if response.status_code == 200:
        data = response.json()
        logger.info(f"✓ Payment Initiated:")
        logger.info(f"  - Amount: KES {data.get('amount')}")
        logger.info(f"  - CheckoutRequestID: {data.get('checkout_request_id')}")
        logger.info(f"  - Message: {data.get('message')}")
        return data
    else:
        logger.error(f"✗ Failed to initiate custom amount payment: {response.json()}")
        return None


def test_invalid_payment_scenarios(client, token, bnpl_user):
    """Test invalid payment scenarios."""
    logger.info("\n=== Testing Invalid Payment Scenarios ===")
    
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    
    # Test 1: Amount exceeding balance
    logger.info("\nTest 1: Amount exceeding balance")
    exceed_amount = float(bnpl_user.current_balance) * 2
    response = client.post(
        '/api/payments/bnpl/pay_balance/',
        data={'phone_number': bnpl_user.phone_number, 'amount': exceed_amount},
        format='json'
    )
    if response.status_code != 200:
        logger.info(f"✓ Correctly rejected: {response.json().get('detail')}")
    else:
        logger.error(f"✗ Should have rejected amount exceeding balance")
    
    # Test 2: Zero amount
    logger.info("\nTest 2: Zero amount")
    response = client.post(
        '/api/payments/bnpl/pay_balance/',
        data={'phone_number': bnpl_user.phone_number, 'amount': 0},
        format='json'
    )
    if response.status_code != 200:
        logger.info(f"✓ Correctly rejected: {response.json().get('detail')}")
    else:
        logger.error(f"✗ Should have rejected zero amount")
    
    # Test 3: Negative amount
    logger.info("\nTest 3: Negative amount")
    response = client.post(
        '/api/payments/bnpl/pay_balance/',
        data={'phone_number': bnpl_user.phone_number, 'amount': -100},
        format='json'
    )
    if response.status_code != 200:
        logger.info(f"✓ Correctly rejected: {response.json().get('detail')}")
    else:
        logger.error(f"✗ Should have rejected negative amount")


def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("BNPL Payment Functionality Test Suite")
    logger.info("=" * 60)
    
    # Create test user
    user, token, bnpl_user = create_test_user()
    
    # Initialize API client
    client = APIClient()
    
    try:
        # Run tests
        test_get_bnpl_status(client, token)
        test_check_pending_payment(client, token)
        test_pay_full_balance(client, token, bnpl_user)
        
        # Refresh user
        bnpl_user.refresh_from_db()
        logger.info(f"\nAfter payment - Balance: KES {bnpl_user.current_balance}")
        
        test_invalid_payment_scenarios(client, token, bnpl_user)
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ All tests completed!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"✗ Test failed with error: {str(e)}", exc_info=True)
    
    finally:
        # Cleanup
        logger.info("\nCleaning up test data...")
        user.delete()
        logger.info("✓ Test user deleted")


if __name__ == '__main__':
    main()
