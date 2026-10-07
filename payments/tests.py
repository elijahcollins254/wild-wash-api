from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from orders.models import Order
from .models import Payment
from .views import BNPLViewSet, MpesaSTKPushView


class OrderPartialPaymentTests(TestCase):
	def setUp(self):
		user_model = get_user_model()
		self.user = user_model.objects.create_user(username='partial-payer', password='test-password')
		self.order = Order.objects.create(
			user=self.user,
			pickup_address='Pickup address',
			dropoff_address='Dropoff address',
			price=Decimal('1000.00'),
		)

	def create_payment(self, amount, payment_status=Payment.STATUS_SUCCESS):
		return Payment.objects.create(
			user=self.user,
			order=self.order,
			amount=Decimal(amount),
			phone_number='254712345678',
			provider='mpesa',
			status=payment_status,
		)

	def test_partial_payment_uses_estimate_until_staff_sets_final_price(self):
		self.create_payment('300.00')

		summary = self.order.get_payment_summary()
		self.assertEqual(summary['final_total'], 1000.0)
		self.assertEqual(summary['paid_amount'], 300.0)
		self.assertEqual(summary['remaining_amount'], 700.0)
		self.assertEqual(summary['paid_percent'], 30)
		self.assertFalse(summary['price_finalized'])
		self.assertFalse(self.order.is_paid())

		self.order.washer_price = Decimal('1200.00')
		self.order.washed_at = timezone.now()
		self.order.save(update_fields=['washer_price', 'washed_at'])

		summary = self.order.get_payment_summary()
		self.assertEqual(summary['final_total'], 1200.0)
		self.assertEqual(summary['remaining_amount'], 900.0)
		self.assertTrue(summary['price_finalized'])

	def test_pending_payment_reduces_payable_but_not_paid_progress(self):
		self.create_payment('300.00')
		self.create_payment('200.00', Payment.STATUS_INITIATED)

		summary = self.order.get_payment_summary()
		self.assertEqual(summary['paid_amount'], 300.0)
		self.assertEqual(summary['pending_amount'], 200.0)
		self.assertEqual(summary['remaining_amount'], 700.0)
		self.assertEqual(summary['payable_amount'], 500.0)

	def test_payment_validators_allow_partial_amounts_and_block_overpayment(self):
		self.create_payment('300.00')

		self.assertIsNone(MpesaSTKPushView()._validate_mpesa_order_amount(self.order, Decimal('700.00')))
		mpesa_error = MpesaSTKPushView()._validate_mpesa_order_amount(self.order, Decimal('700.01'))
		bnpl_error = BNPLViewSet()._validate_bnpl_order_amount(self.order, Decimal('700.01'))

		self.assertEqual(mpesa_error.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(bnpl_error.status_code, status.HTTP_400_BAD_REQUEST)

	def test_is_paid_requires_successful_payments_to_cover_final_total(self):
		self.create_payment('1000.00')
		self.assertFalse(self.order.is_paid())

		self.order.washer_price = Decimal('1200.00')
		self.order.washed_at = timezone.now()
		self.order.save(update_fields=['washer_price', 'washed_at'])
		self.assertFalse(self.order.is_paid())

		self.create_payment('200.00')
		self.assertTrue(self.order.is_paid())
