from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from django.utils import timezone

from .models import Offer, OfferNotificationSubscription, Banner


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


class OfferImageTests(APITestCase):
    def test_offer_image_url_is_exposed_by_public_detail_endpoint(self):
        offer = Offer.objects.create(
            title='Spring cleaning',
            description='Save on home cleaning.',
            code='SPRING',
            valid_from=timezone.now(),
            image_url='https://cdn.example.com/offers/spring.jpg',
        )

        response = self.client.get(f'/offers/{offer.id}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['image_url'], offer.image_url)


class BannerTests(APITestCase):
    def test_active_banner_is_exposed_publicly(self):
        banner = Banner.objects.create(
            title='Android app',
            image_url='https://cdn.example.com/banner.png',
            button_text='Install app',
            link_url='https://play.google.com/store/apps/details?id=com.kibeezy.ww',
        )

        response = self.client.get('/offers/banners')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.data
        items = payload['results'] if isinstance(payload, dict) and 'results' in payload else payload
        self.assertTrue(any(item['id'] == banner.id for item in items))
