from django.test import TestCase
from django.contrib.auth import get_user_model
from typing import Any, cast
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from rest_framework.reverse import reverse

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
