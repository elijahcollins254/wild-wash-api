from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from .models import OfferNotificationSubscription


User = get_user_model()
SUBSCRIPTION_URL = '/offers/subscriptions/my_subscription'


class OfferNotificationSubscriptionTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='offer_subscriber',
            phone='0718693484',
            password='StrongPass123',
        )
        self.client.force_authenticate(user=self.user)

    def test_subscribe_reuses_unowned_subscription_for_same_phone(self):
        existing = OfferNotificationSubscription.objects.create(
            phone_number=self.user.phone,
            is_active=False,
        )

        response = self.client.post(SUBSCRIPTION_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(OfferNotificationSubscription.objects.count(), 1)
        existing.refresh_from_db()
        self.assertEqual(existing.user, self.user)
        self.assertTrue(existing.is_active)

    def test_subscribe_rejects_phone_linked_to_another_user(self):
        other_user = User.objects.create_user(
            username='another_offer_subscriber',
            phone=self.user.phone,
            password='StrongPass123',
        )
        existing = OfferNotificationSubscription.objects.create(
            user=other_user,
            phone_number=self.user.phone,
        )

        response = self.client.post(SUBSCRIPTION_URL)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        existing.refresh_from_db()
        self.assertEqual(existing.user, other_user)

    def test_subscribe_creates_a_subscription_and_is_idempotent(self):
        first_response = self.client.post(SUBSCRIPTION_URL)
        second_response = self.client.post(SUBSCRIPTION_URL)

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(OfferNotificationSubscription.objects.count(), 1)
