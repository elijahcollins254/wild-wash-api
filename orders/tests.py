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


class OrderLaundryAssignmentTests(TestCase):
	def setUp(self):
		suffix = uuid4().hex
		self.location = Location.objects.create(name=f'Laundry {suffix}', region='Nairobi')
		self.order = Order.objects.create(
			code=f'WW-ASSIGN-{suffix[:20]}',
			pickup_address='Customer pickup',
			dropoff_address='Customer dropoff',
		)
		self.admin = User.objects.create_user(
			username=f'location_admin_{suffix}',
			password='testpass123',
			is_staff=True,
			is_superuser=True,
		)
		self.client = APIClient()

	def test_superuser_can_assign_order_to_active_laundry(self):
		self.client.force_authenticate(user=self.admin)

		response = self.client.post('/orders/assign-location/', {
			'order_id': self.order.id,
			'service_location_id': self.location.id,
		}, format='json')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data['service_location']['id'], self.location.id)
		self.order.refresh_from_db()
		self.assertEqual(self.order.service_location, self.location)

	def test_non_superuser_cannot_assign_laundry(self):
		staff = User.objects.create_user(
			username=f'regular_staff_{uuid4().hex}',
			password='testpass123',
			is_staff=True,
			service_location=self.location,
		)
		self.client.force_authenticate(user=staff)

		response = self.client.post('/orders/assign-location/', {
			'order_id': self.order.id,
			'service_location_id': self.location.id,
		}, format='json')

		self.assertEqual(response.status_code, 403)
		self.order.refresh_from_db()
		self.assertIsNone(self.order.service_location)

	def test_inactive_laundry_cannot_be_assigned(self):
		self.location.is_active = False
		self.location.save(update_fields=['is_active'])
		self.client.force_authenticate(user=self.admin)

		response = self.client.post('/orders/assign-location/', {
			'order_id': self.order.id,
			'service_location_id': self.location.id,
		}, format='json')

		self.assertEqual(response.status_code, 404)
		self.order.refresh_from_db()
		self.assertIsNone(self.order.service_location)


class OrderCodeSecurityTest(TestCase):
	def test_new_orders_receive_long_random_codes(self):
		first_order = Order.objects.create(
			pickup_address='Pickup',
			dropoff_address='Dropoff',
		)
		second_order = Order.objects.create(
			pickup_address='Pickup',
			dropoff_address='Dropoff',
		)

		self.assertRegex(first_order.code, r'^WW-[A-F0-9]{29}$')
		self.assertRegex(second_order.code, r'^WW-[A-F0-9]{29}$')
		self.assertNotEqual(first_order.code, second_order.code)
		from .serializers import OrderCreateSerializer
		self.assertEqual(OrderCreateSerializer(first_order).data['code'], first_order.code)

	def test_customer_cannot_look_up_another_customers_order_by_code(self):
		suffix = uuid4().hex
		owner = User.objects.create_user(username=f'order_owner_{suffix}', password='testpass123')
		other_customer = User.objects.create_user(username=f'other_customer_{suffix}', password='testpass123')
		order = Order.objects.create(
			user=owner,
			code=f'WW-PRIVATE-{suffix[:16]}',
			pickup_address='Pickup',
			dropoff_address='Dropoff',
		)

		client = APIClient()
		client.force_authenticate(user=other_customer)
		response = client.get(f'/orders/?code={order.code}')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data['count'], 0)
