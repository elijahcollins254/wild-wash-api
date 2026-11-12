from unittest import TestCase
from uuid import uuid4

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from unittest.mock import patch

from .models import Order
from users.models import Location
from notifications.models import Notification

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
			washer=washer,
		)
		unassigned_order = Order.objects.create(
			code=f'WW-UNASSIGNED-{suffix[:18]}',
			user=customer,
			service_location=location,
			pickup_address='Unassigned pickup',
			dropoff_address='Unassigned dropoff',
		)
		other_washer = User.objects.create_user(
			username=f'other_role_washer_{suffix}',
			password='testpass123',
			role='washer',
			service_location=location,
		)
		other_assigned_order = Order.objects.create(
			code=f'WW-OTHER-WASHER-{suffix[:15]}',
			user=customer,
			service_location=location,
			pickup_address='Other washer pickup',
			dropoff_address='Other washer dropoff',
			washer=other_washer,
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
		self.assertNotEqual(response.data['results'][0]['id'], unassigned_order.id)
		self.assertNotEqual(response.data['results'][0]['id'], other_assigned_order.id)


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


class WasherOrderAssignmentTests(TestCase):
	def setUp(self):
		suffix = uuid4().hex
		self.location = Location.objects.create(name=f'Washer assignment {suffix}')
		self.admin = User.objects.create_user(
			username=f'washer_admin_{suffix}',
			password='testpass123',
			role='admin',
			is_staff=True,
		)
		self.washer = User.objects.create_user(
			username=f'washer_{suffix}',
			password='testpass123',
			role='washer',
			staff_type='washer',
			service_location=self.location,
			phone='0712345678',
		)
		self.order = Order.objects.create(
			code=f'WW-WASHER-{suffix[:18]}',
			status='in_progress',
			service_location=self.location,
			pickup_address='Pickup',
			dropoff_address='Dropoff',
		)
		self.client = APIClient()

	@patch('services.sms_service.AfricasTalkingSMSService')
	def test_admin_assigns_washer_creates_notification_and_sends_sms(self, sms_service_class):
		sms_service_class.return_value.send_sms.return_value = {'status': 'success'}
		self.client.force_authenticate(user=self.admin)

		response = self.client.post('/orders/assign-washer/', {
			'order_id': self.order.id,
			'washer_id': self.washer.id,
		}, format='json')

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.data['sms_sent'])
		self.order.refresh_from_db()
		self.assertEqual(self.order.washer, self.washer)
		self.assertTrue(Notification.objects.filter(
			user=self.washer,
			order=self.order,
			notification_type='order_assigned',
		).exists())
		sms_service_class.return_value.send_sms.assert_called_once()
		sms_args = sms_service_class.return_value.send_sms.call_args.kwargs
		self.assertEqual(sms_args['phone_number'], self.washer.phone)
		self.assertIn(self.order.code, sms_args['message'])

	def test_non_admin_cannot_assign_washer(self):
		customer = User.objects.create_user(username=f'customer_{uuid4().hex}', password='testpass123')
		self.client.force_authenticate(user=customer)

		response = self.client.post('/orders/assign-washer/', {
			'order_id': self.order.id,
			'washer_id': self.washer.id,
		}, format='json')

		self.assertEqual(response.status_code, 403)
		self.order.refresh_from_db()
		self.assertIsNone(self.order.washer)

	def test_washer_cannot_update_an_order_assigned_to_another_washer(self):
		other_washer = User.objects.create_user(
			username=f'other_washer_{uuid4().hex}',
			password='testpass123',
			role='washer',
			staff_type='washer',
			service_location=self.location,
		)
		self.order.washer = other_washer
		self.order.save(update_fields=['washer'])
		self.client.force_authenticate(user=self.washer)

		response = self.client.patch(
			f'/orders/update/?id={self.order.id}',
			{'status': 'washed'},
			format='json',
		)

		self.assertEqual(response.status_code, 403)
		self.order.refresh_from_db()
		self.assertEqual(self.order.status, 'in_progress')


class OrderCodeSecurityTest(TestCase):
	def test_new_orders_receive_short_grouped_alphanumeric_codes(self):
		first_order = Order.objects.create(
			pickup_address='Pickup',
			dropoff_address='Dropoff',
		)
		second_order = Order.objects.create(
			pickup_address='Pickup',
			dropoff_address='Dropoff',
		)

		self.assertRegex(first_order.code, r'^WW-[A-Z0-9]{3}-[A-Z0-9]{3}-[A-Z0-9]{3}$')
		self.assertRegex(second_order.code, r'^WW-[A-Z0-9]{3}-[A-Z0-9]{3}-[A-Z0-9]{3}$')
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


class OrderRatingTests(TestCase):
	def setUp(self):
		suffix = uuid4().hex
		self.customer = User.objects.create_user(username=f'rating_customer_{suffix}', password='testpass123')
		self.other_customer = User.objects.create_user(username=f'other_rating_customer_{suffix}', password='testpass123')
		self.order = Order.objects.create(
			user=self.customer,
			code=f'WW-RATE-{suffix[:16]}',
			status='delivered',
			pickup_address='Pickup',
			dropoff_address='Dropoff',
		)
		self.client = APIClient()
		self.client.force_authenticate(user=self.customer)
		self.url = f'/orders/{self.order.code}/rating/'

	def test_customer_can_rate_their_delivered_order(self):
		response = self.client.post(self.url, {'rating': 5, 'comment': 'Great service'}, format='json')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data['rating'], 5)
		self.assertEqual(response.data['comment'], 'Great service')
		self.assertEqual(self.order.rating.customer, self.customer)

	def test_customer_can_update_their_rating(self):
		self.client.post(self.url, {'rating': 4}, format='json')

		response = self.client.post(self.url, {'rating': 3, 'comment': 'Updated'}, format='json')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(self.order.rating.rating, 3)
		self.assertEqual(self.order.rating.comment, 'Updated')
		self.assertEqual(self.order.rating.customer, self.customer)

	def test_customer_can_retrieve_their_existing_rating(self):
		self.client.post(self.url, {'rating': 5, 'comment': 'Great'}, format='json')

		response = self.client.get(self.url)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data['rating'], 5)
		self.assertEqual(response.data['comment'], 'Great')

	def test_customer_cannot_rate_another_customers_order(self):
		self.client.force_authenticate(user=self.other_customer)

		response = self.client.post(self.url, {'rating': 5}, format='json')

		self.assertEqual(response.status_code, 403)

	def test_order_must_be_delivered_before_it_can_be_rated(self):
		self.order.status = 'ready'
		self.order.save(update_fields=['status'])

		response = self.client.post(self.url, {'rating': 5}, format='json')

		self.assertEqual(response.status_code, 400)

	def test_rating_must_be_between_one_and_five(self):
		response = self.client.post(self.url, {'rating': 6}, format='json')

		self.assertEqual(response.status_code, 400)
