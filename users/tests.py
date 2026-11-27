from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.test import TestCase
from django.contrib.auth import get_user_model
from typing import Any, cast
from unittest.mock import patch
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from rest_framework.reverse import reverse
from django.test import override_settings
from orders.models import Order, OrderReview

from .models import DataDeletionRequest, PartnerApplication
from .events import USER_COUNT_GROUP


User = get_user_model()


class PublicUserCountApiTests(APITestCase):
	def test_public_count_returns_the_backend_user_count(self):
		User.objects.create_user(username='trusted_count_user', password='StrongPass123')

		response = self.client.get('/users/count/')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['count'], User.objects.count())

	def test_count_events_endpoint_returns_a_public_sse_stream(self):
		response = self.client.get('/users/count/events/')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response['Content-Type'], 'text/event-stream')
		self.assertEqual(response['Cache-Control'], 'no-cache, no-transform')
		self.assertEqual(response['X-Accel-Buffering'], 'no')
		response.close()

	def test_new_user_creation_broadcasts_an_updated_count(self):
		channel_layer = get_channel_layer()
		channel_name = async_to_sync(channel_layer.new_channel)('test-user-count')
		async_to_sync(channel_layer.group_add)(USER_COUNT_GROUP, channel_name)

		try:
			with self.captureOnCommitCallbacks(execute=True):
				User.objects.create_user(
					username='trusted_count_signup',
					password='StrongPass123',
				)

			event = async_to_sync(channel_layer.receive)(channel_name)

			self.assertEqual(event['type'], 'users.count_changed')
			self.assertEqual(event['user_count'], User.objects.count())
		finally:
			async_to_sync(channel_layer.group_discard)(USER_COUNT_GROUP, channel_name)


class DataDeletionRequestApiTests(APITestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username='requester',
			email='requester@example.com',
			phone='0712345678',
			password='StrongPass123',
		)
		self.api_client = APIClient()
		self.url = reverse('deletion-request-create')

	def test_request_requires_authentication(self):
		response = cast(Any, self.api_client.post(self.url, {'request_type': 'account'}, format='json'))

		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
		self.assertEqual(DataDeletionRequest.objects.count(), 0)

	def test_authenticated_account_deletion_request_is_recorded(self):
		self.api_client.force_authenticate(user=self.user)

		response = cast(Any, self.api_client.post(self.url, {'request_type': 'account'}, format='json'))

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		request_record = DataDeletionRequest.objects.get()
		self.assertEqual(request_record.user, self.user)
		self.assertEqual(request_record.account_email, self.user.email)
		self.assertEqual(request_record.account_phone, getattr(self.user, 'phone'))
		self.assertEqual(request_record.status, 'pending')

	def test_selected_data_request_requires_details(self):
		self.api_client.force_authenticate(user=self.user)

		response = cast(Any, self.api_client.post(self.url, {'request_type': 'data'}, format='json'))

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertFalse(DataDeletionRequest.objects.exists())

	def test_regular_user_cannot_use_generic_user_delete_endpoint(self):
		target_user = User.objects.create_user(username='target', password='StrongPass123')
		self.api_client.force_authenticate(user=self.user)

		response = cast(Any, self.api_client.delete(reverse('user-detail', kwargs={'pk': target_user.pk})))

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
		self.assertTrue(User.objects.filter(pk=target_user.pk).exists())


class MobileGoogleAuthApiTests(APITestCase):
	def setUp(self):
		self.api_client = APIClient()
		self.url = reverse('google-auth-mobile')

	@override_settings(GOOGLE_OAUTH_CLIENT_IDS=('wildwash-mobile-client',))
	@patch('users.views.google_id_token.verify_oauth2_token')
	def test_valid_google_token_creates_user_and_returns_api_token(self, mock_verify):
		mock_verify.return_value = {
			'aud': 'wildwash-mobile-client',
			'email_verified': 'true',
			'email': 'newuser@example.com',
			'name': 'New User',
			'sub': 'google-subject',
		}

		response = cast(Any, self.api_client.post(self.url, {'id_token': 'signed-id-token'}, format='json'))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['user']['email'], 'newuser@example.com')
		self.assertTrue(response.data['token'])
		self.assertTrue(User.objects.filter(email='newuser@example.com').exists())
		mock_verify.assert_called_once()

	@override_settings(GOOGLE_OAUTH_CLIENT_IDS=('wildwash-mobile-client',))
	@patch('users.views.google_id_token.verify_oauth2_token')
	def test_token_for_another_client_is_rejected(self, mock_verify):
		mock_verify.return_value = {
			'aud': 'another-client',
			'email_verified': 'true',
			'email': 'attacker@example.com',
			'sub': 'google-subject',
		}

		response = cast(Any, self.api_client.post(self.url, {'id_token': 'signed-id-token'}, format='json'))

		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
		self.assertFalse(User.objects.filter(email='attacker@example.com').exists())

	def test_missing_id_token_is_rejected(self):
		response = cast(Any, self.api_client.post(self.url, {}, format='json'))

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class RegistrationPhoneValidationTests(APITestCase):
	def test_registration_accepts_kenyan_01_number_and_normalizes_it(self):
		response = self.client.post('/users/register/', {
			'username': 'kenya_phone_user',
			'phone': '0116629591',
			'password': 'StrongPass123',
		}, format='json')

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data['phone'], '+254116629591')
		self.assertEqual(User.objects.get(username='kenya_phone_user').phone, '+254116629591')

	def test_registration_rejects_an_existing_phone_in_another_format(self):
		User.objects.create_user(
			username='existing_phone_user',
			phone='+254116629591',
			password='StrongPass123',
		)

		response = self.client.post('/users/register/', {
			'username': 'duplicate_phone_user',
			'phone': '0116629591',
			'password': 'StrongPass123',
		}, format='json')

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('phone', response.data)
		self.assertFalse(User.objects.filter(username='duplicate_phone_user').exists())


class UserProfilePatchTests(APITestCase):
	def test_partial_update_handles_null_profile_fields(self):
		user = User.objects.create_user(username='profile_patch_user', password='StrongPass123')
		self.client.force_authenticate(user=user)

		response = self.client.patch('/users/me/', {'first_name': 'Alex'}, format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		user.refresh_from_db()
		self.assertEqual(user.first_name, 'Alex')
		self.assertFalse(user.profile_complete)

	def test_profile_update_rejects_another_users_phone(self):
		user = User.objects.create_user(username='profile_patch_user', password='StrongPass123')
		User.objects.create_user(
			username='phone_owner',
			phone='0712345678',
			password='StrongPass123',
		)
		self.client.force_authenticate(user=user)

		response = self.client.patch('/users/me/', {'phone': '0712345678'}, format='json')

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('phone', response.data)
		user.refresh_from_db()
		self.assertIsNone(user.phone)

	def test_profile_patch_cannot_grant_staff_role(self):
		user = User.objects.create_user(username='partner_applicant', password='StrongPass123')
		self.client.force_authenticate(user=user)

		response = self.client.patch('/users/me/', {'role': 'washer', 'staff_type': 'washer'}, format='json')

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
		user.refresh_from_db()
		self.assertEqual(user.role, 'customer')
		self.assertEqual(user.staff_type, 'general')

	def test_user_endpoint_does_not_allow_applicant_to_change_own_role(self):
		user = User.objects.create_user(username='partner_user_update', password='StrongPass123')
		self.client.force_authenticate(user=user)

		response = self.client.patch(
			f'/users/users/{user.id}/',
			{'role': 'washer', 'staff_type': 'washer'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
		user.refresh_from_db()
		self.assertEqual(user.role, 'customer')


class PartnerApplicationApiTests(APITestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='partner_applicant', password='StrongPass123')
		self.client.force_authenticate(user=self.user)
		self.application_data = {
			'first_name': 'Alex',
			'last_name': 'Kimani',
			'phone': '0712345678',
			'email': 'alex@example.com',
			'business_name': 'Fresh Fold',
			'business_type': 'Laundry shop',
			'location': 'Westlands',
			'pickup_address': 'Market Street',
			'service_area': 'Westlands and Parklands',
			'machine_count': 3,
			'pickup_latitude': '-1.267000',
			'pickup_longitude': '36.810000',
		}

	def test_authenticated_user_can_submit_one_application(self):
		response = self.client.post('/users/partner-applications/', self.application_data, format='json')

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data['status'], 'pending')
		self.assertEqual(response.data['business_name'], 'Fresh Fold')
		self.assertEqual(response.data['user'], self.user.id)
		self.user.refresh_from_db()
		self.assertEqual(self.user.role, 'customer')

		duplicate_response = self.client.post('/users/partner-applications/', self.application_data, format='json')
		self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_only_admin_can_approve_and_approval_populates_partner_profile(self):
		create_response = self.client.post('/users/partner-applications/', self.application_data, format='json')
		application_id = create_response.data['id']

		self.assertEqual(
			self.client.post(f'/users/partner-applications/{application_id}/approve/', {}, format='json').status_code,
			status.HTTP_403_FORBIDDEN,
		)

		admin = User.objects.create_user(username='partner_admin', password='StrongPass123', is_staff=True)
		self.client.force_authenticate(user=admin)
		approve_response = self.client.post(
			f'/users/partner-applications/{application_id}/approve/',
			{'notes': 'Approved'},
			format='json',
		)

		self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
		self.user.refresh_from_db()
		self.assertEqual(self.user.role, 'washer')
		self.assertEqual(self.user.staff_type, 'washer')
		self.assertEqual(self.user.business_name, 'Fresh Fold')
		self.assertEqual(self.user.service_area, 'Westlands and Parklands')
		self.assertEqual(self.user.machine_count, 3)

	def test_applicant_cannot_approve_another_application(self):
		other_user = User.objects.create_user(username='other_applicant', password='StrongPass123')
		application = PartnerApplication.objects.create(
			user=other_user,
			first_name='Sam',
			last_name='Wanjiku',
			phone='0712345679',
			email='sam@example.com',
			business_name='Clean Clothes',
			business_type='Laundry shop',
			location='Kilimani',
			pickup_address='Kilimani Road',
			service_area='Kilimani',
			machine_count=2,
		)
		self.client.force_authenticate(user=self.user)

		response = self.client.post(f'/users/partner-applications/{application.id}/approve/', {}, format='json')

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
		other_user.refresh_from_db()
		self.assertEqual(other_user.role, 'customer')

	def test_admin_list_includes_partner_activity_and_ratings(self):
		application_response = self.client.post('/users/partner-applications/', self.application_data, format='json')
		customer = User.objects.create_user(username='partner_customer', password='StrongPass123')
		active_order = Order.objects.create(
			user=customer,
			washer=self.user,
			pickup_address='Customer address',
			dropoff_address='Customer address',
			status='in_progress',
		)
		delivered_order = Order.objects.create(
			user=customer,
			washer=self.user,
			pickup_address='Customer address',
			dropoff_address='Customer address',
			status='delivered',
		)
		OrderReview.objects.create(order=delivered_order, customer=customer, rating=4)
		admin = User.objects.create_user(username='partner_admin', password='StrongPass123', is_staff=True)
		self.client.force_authenticate(user=admin)

		response = self.client.get('/users/partner-applications/')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		application_data = response.data['results'][0]
		self.assertEqual(application_data['id'], application_response.data['id'])
		self.assertEqual(application_data['active_order_count'], 1)
		self.assertEqual(application_data['completed_order_count'], 1)
		self.assertEqual(float(application_data['average_rating']), 4.0)
		self.assertEqual(application_data['rating_count'], 1)

	def test_admin_can_bulk_disable_and_activate_approved_partners(self):
		application_response = self.client.post('/users/partner-applications/', self.application_data, format='json')
		admin = User.objects.create_user(username='partner_admin', password='StrongPass123', is_staff=True)
		self.client.force_authenticate(user=admin)
		self.client.post(
			f"/users/partner-applications/{application_response.data['id']}/approve/",
			{},
			format='json',
		)
		bulk_url = '/users/partner-applications/bulk-account-status/'
		payload = {'application_ids': [application_response.data['id']], 'is_active': False}

		disable_response = self.client.post(bulk_url, payload, format='json')

		self.assertEqual(disable_response.status_code, status.HTTP_200_OK)
		self.assertEqual(disable_response.data['updated_count'], 1)
		self.user.refresh_from_db()
		self.assertFalse(self.user.is_active)

		payload['is_active'] = True
		activate_response = self.client.post(bulk_url, payload, format='json')
		self.assertEqual(activate_response.status_code, status.HTTP_200_OK)
		self.user.refresh_from_db()
		self.assertTrue(self.user.is_active)

	def test_bulk_account_status_cannot_include_pending_application(self):
		application_response = self.client.post('/users/partner-applications/', self.application_data, format='json')
		admin = User.objects.create_user(username='partner_admin', password='StrongPass123', is_staff=True)
		self.client.force_authenticate(user=admin)

		response = self.client.post(
			'/users/partner-applications/bulk-account-status/',
			{'application_ids': [application_response.data['id']], 'is_active': False},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.user.refresh_from_db()
		self.assertTrue(self.user.is_active)

	def test_rejected_application_can_be_resubmitted_without_activating_role(self):
		create_response = self.client.post('/users/partner-applications/', self.application_data, format='json')
		admin = User.objects.create_user(username='partner_admin', password='StrongPass123', is_staff=True)
		self.client.force_authenticate(user=admin)

		reject_response = self.client.post(
			f"/users/partner-applications/{create_response.data['id']}/reject/",
			{'notes': 'Please clarify your service area.'},
			format='json',
		)

		self.assertEqual(reject_response.status_code, status.HTTP_200_OK)
		self.assertEqual(reject_response.data['reviewer_notes'], 'Please clarify your service area.')
		self.user.refresh_from_db()
		self.assertEqual(self.user.role, 'customer')

		self.client.force_authenticate(user=self.user)
		resubmit_response = self.client.post('/users/partner-applications/', self.application_data, format='json')
		self.assertEqual(resubmit_response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(resubmit_response.data['status'], 'pending')
