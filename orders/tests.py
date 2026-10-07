from unittest import TestCase
from uuid import uuid4

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from .models import Order
from users.models import Location

User = get_user_model()


class OrderStatusChoiceTest(TestCase):
	def test_any_defined_status_can_follow_any_current_status(self):
		order = Order(status='assigned_pickup')
		valid_statuses = [value for value, _label in Order.STATUS_CHOICES]

		for current_status in valid_statuses:
			order.status = current_status
			for new_status in valid_statuses:
				with self.subTest(current=current_status, new=new_status):
					self.assertTrue(order.can_transition_to(new_status))

	def test_unknown_status_is_rejected(self):
		order = Order(status='assigned_pickup')

		self.assertFalse(order.can_transition_to('in_progress_typo'))
		self.assertFalse(order.can_transition_to(None))


class StaffOrderListTest(TestCase):
	def test_role_based_washer_sees_orders_for_assigned_location(self):
		suffix = uuid4().hex
		location = Location.objects.create(name=f'Washer location {suffix}')
		other_location = Location.objects.create(name=f'Other location {suffix}')
		customer = User.objects.create_user(username=f'order_customer_{suffix}', password='testpass123')
		washer = User.objects.create_user(
			username=f'role_washer_{suffix}',
			password='testpass123',
			role='washer',
			service_location=location,
			is_staff=False,
		)
		self.assertFalse(washer.is_staff)
		local_order = Order.objects.create(
			code=f'WW-LOCAL-{suffix[:20]}',
			user=customer,
			service_location=location,
			pickup_address='Local pickup',
			dropoff_address='Local dropoff',
		)
		Order.objects.create(
			code=f'WW-OTHER-{suffix[:20]}',
			user=customer,
			service_location=other_location,
			pickup_address='Other pickup',
			dropoff_address='Other dropoff',
		)

		client = APIClient()
		client.force_authenticate(user=washer)
		response = client.get('/orders/')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data['count'], 1)
		self.assertEqual(response.data['results'][0]['id'], local_order.id)
