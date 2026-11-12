from django.test import TestCase
from django.contrib.auth import get_user_model
from typing import Any, cast
from unittest.mock import patch
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from rest_framework.reverse import reverse
from django.test import override_settings

from .models import DataDeletionRequest


User = get_user_model()


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
