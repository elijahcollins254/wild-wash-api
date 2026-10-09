from django.test import TestCase
from django.test import override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from unittest.mock import patch
from decimal import Decimal

from .models import (
	RiderWallet, RiderWalletTransaction,
	WasherWallet, WasherWalletTransaction,
)


User = get_user_model()


class RiderWalletApiTests(TestCase):
	def setUp(self):
		self.rider = User.objects.create_user(username='wallet_rider', password='pass1234', role='rider', phone='+254712345678')
		self.admin = User.objects.create_superuser(username='wallet_admin', password='pass1234', email='admin@example.com')
		self.customer = User.objects.create_user(username='wallet_customer', password='pass1234', role='customer')
		self.client = APIClient()
		self.wallet = RiderWallet.objects.create(rider=self.rider, balance=Decimal('1200.00'), payout_phone='254712345678')

	def test_rider_can_read_own_wallet_but_customer_cannot(self):
		self.client.force_authenticate(self.rider)
		response = self.client.get('/riders/wallet/me/')
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data['balance'], '1200.00')

		self.client.force_authenticate(self.customer)
		response = self.client.get('/riders/wallet/me/')
		self.assertEqual(response.status_code, 403)

	def test_admin_credit_requires_reason_and_audits_admin(self):
		self.client.force_authenticate(self.admin)
		response = self.client.post(f'/riders/wallets/{self.rider.id}/credit/', {'amount': '250', 'reason': 'weekly earnings'}, format='json')
		self.assertEqual(response.status_code, 201)
		self.wallet.refresh_from_db()
		self.assertEqual(self.wallet.balance, Decimal('1450.00'))
		entry = RiderWalletTransaction.objects.get(transaction_type='credit')
		self.assertEqual(entry.created_by, self.admin)

		response = self.client.post(f'/riders/wallets/{self.rider.id}/credit/', {'amount': '50'}, format='json')
		self.assertEqual(response.status_code, 400)

	@override_settings(
		MPESA_ENVIRONMENT='sandbox',
		MPESA_SANDBOX_CONSUMER_KEY='sandbox-key',
		MPESA_SANDBOX_CONSUMER_SECRET='sandbox-secret',
		MPESA_B2C_INITIATOR_NAME='test-initiator',
		MPESA_B2C_SECURITY_CREDENTIAL='encrypted-test-credential',
		MPESA_B2C_RESULT_URL='https://example.test/result/',
		MPESA_B2C_TIMEOUT_URL='https://example.test/timeout/',
		MPESA_B2C_CALLBACK_TOKEN='test-callback-token',
	)
	@patch('riders.views._submit_b2c_payout', return_value={'ResponseCode': '0', 'ConversationID': 'conversation-1', 'OriginatorConversationID': 'origin-1'})
	def test_withdrawal_reserves_balance_and_callback_completes_it(self, submit_payout):
		self.client.force_authenticate(self.rider)
		response = self.client.post('/riders/wallet/me/', {'amount': 500}, format='json')
		self.assertEqual(response.status_code, 202)
		self.wallet.refresh_from_db()
		self.assertEqual(self.wallet.balance, Decimal('700.00'))
		payout = RiderWalletTransaction.objects.get(transaction_type='withdrawal')
		self.assertEqual(payout.status, 'pending')
		submit_payout.assert_called_once()

		callback = self.client.post('/riders/mpesa/b2c/result/?token=test-callback-token', {
			'Result': {
				'ResultCode': 0,
				'OriginatorConversationID': 'origin-1',
				'ConversationID': 'conversation-1',
				'TransactionID': 'QWE123',
			}
		}, format='json')
		self.assertEqual(callback.status_code, 200)
		payout.refresh_from_db()
		self.assertEqual(payout.status, 'completed')

	@override_settings(
		MPESA_ENVIRONMENT='sandbox',
		MPESA_SANDBOX_CONSUMER_KEY='sandbox-key',
		MPESA_SANDBOX_CONSUMER_SECRET='sandbox-secret',
		MPESA_B2C_INITIATOR_NAME='test-initiator',
		MPESA_B2C_SECURITY_CREDENTIAL='encrypted-test-credential',
		MPESA_B2C_RESULT_URL='https://example.test/result/',
		MPESA_B2C_TIMEOUT_URL='https://example.test/timeout/',
		MPESA_B2C_CALLBACK_TOKEN='test-callback-token',
	)
	@patch('riders.views._submit_b2c_payout', side_effect=RuntimeError('Rejected'))
	def test_confirmed_submission_failure_reverses_wallet_amount(self, submit_payout):
		self.client.force_authenticate(self.rider)
		response = self.client.post('/riders/wallet/me/', {'amount': 500}, format='json')
		self.assertEqual(response.status_code, 502)
		self.wallet.refresh_from_db()
		self.assertEqual(self.wallet.balance, Decimal('1200.00'))
		self.assertTrue(RiderWalletTransaction.objects.filter(transaction_type='reversal', status='completed').exists())


class WasherWalletApiTests(TestCase):
	def setUp(self):
		self.washer = User.objects.create_user(username='wallet_washer', password='pass1234', role='staff', staff_type='washer', phone='+254712345679')
		self.admin = User.objects.create_superuser(username='washer_wallet_admin', password='pass1234', email='washer-admin@example.com')
		self.customer = User.objects.create_user(username='washer_wallet_customer', password='pass1234', role='customer')
		self.client = APIClient()
		self.wallet = WasherWallet.objects.create(washer=self.washer, balance=Decimal('1200.00'), payout_phone='254712345679')

	def test_washer_can_read_wallet_but_customer_cannot(self):
		self.client.force_authenticate(self.washer)
		response = self.client.get('/riders/washer-wallet/me/')
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data['balance'], '1200.00')

		self.client.force_authenticate(self.customer)
		response = self.client.get('/riders/washer-wallet/me/')
		self.assertEqual(response.status_code, 403)

	def test_admin_credit_records_washer_wallet_audit(self):
		self.client.force_authenticate(self.admin)
		response = self.client.post(
			f'/riders/washer-wallets/{self.washer.id}/credit/',
			{'amount': '250', 'reason': 'weekly washing commission'},
			format='json',
		)
		self.assertEqual(response.status_code, 201)
		self.wallet.refresh_from_db()
		self.assertEqual(self.wallet.balance, Decimal('1450.00'))
		entry = WasherWalletTransaction.objects.get(transaction_type='credit')
		self.assertEqual(entry.created_by, self.admin)

	@override_settings(
		MPESA_ENVIRONMENT='sandbox',
		MPESA_SANDBOX_CONSUMER_KEY='sandbox-key',
		MPESA_SANDBOX_CONSUMER_SECRET='sandbox-secret',
		MPESA_B2C_INITIATOR_NAME='test-initiator',
		MPESA_B2C_SECURITY_CREDENTIAL='encrypted-test-credential',
		MPESA_B2C_RESULT_URL='https://example.test/result/',
		MPESA_B2C_TIMEOUT_URL='https://example.test/timeout/',
		MPESA_B2C_CALLBACK_TOKEN='test-callback-token',
	)
	@patch('riders.views._submit_b2c_payout', return_value={'ResponseCode': '0', 'ConversationID': 'washer-conversation', 'OriginatorConversationID': 'washer-origin'})
	def test_washer_withdrawal_uses_b2c_and_callback_completes_it(self, submit_payout):
		self.client.force_authenticate(self.washer)
		response = self.client.post('/riders/washer-wallet/me/', {'amount': 500}, format='json')
		self.assertEqual(response.status_code, 202)
		self.wallet.refresh_from_db()
		self.assertEqual(self.wallet.balance, Decimal('700.00'))
		payout = WasherWalletTransaction.objects.get(transaction_type='withdrawal')
		self.assertEqual(payout.status, 'pending')
		submit_payout.assert_called_once()

		callback = self.client.post('/riders/mpesa/b2c/result/?token=test-callback-token', {
			'Result': {
				'ResultCode': 0,
				'OriginatorConversationID': 'washer-origin',
				'ConversationID': 'washer-conversation',
				'TransactionID': 'WAS123',
			}
		}, format='json')
		self.assertEqual(callback.status_code, 200)
		payout.refresh_from_db()
		self.assertEqual(payout.status, 'completed')
