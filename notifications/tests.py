from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import Mock, patch

from users.models import User

from .models import Notification, PushDevice
from .push import EXPO_PUSH_URL, send_notification_push


class PushDeviceApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='push-user', password='password')
        self.other_user = User.objects.create_user(username='other-user', password='password')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.token = 'ExpoPushToken[device_token_123]'

    def test_register_reassigns_token_to_current_user(self):
        device = PushDevice.objects.create(
            user=self.other_user,
            token=self.token,
            platform='android',
            is_active=False,
        )

        response = self.client.post(
            '/notifications/devices/',
            {'token': self.token, 'platform': 'android'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        device.refresh_from_db()
        self.assertEqual(device.user, self.user)
        self.assertTrue(device.is_active)

    def test_registration_rejects_non_expo_token(self):
        response = self.client.post(
            '/notifications/devices/',
            {'token': 'not-a-token', 'platform': 'android'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PushDevice.objects.exists())

    def test_unregister_only_deactivates_current_users_device(self):
        device = PushDevice.objects.create(
            user=self.other_user,
            token=self.token,
            platform='android',
        )

        response = self.client.delete(
            '/notifications/devices/',
            {'token': self.token, 'platform': 'android'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        device.refresh_from_db()
        self.assertTrue(device.is_active)


class PushDeliveryTests(TestCase):
    def test_notification_is_sent_to_active_device(self):
        user = User.objects.create_user(username='push-recipient', password='password')
        device = PushDevice.objects.create(
            user=user,
            token='ExpoPushToken[device_token_123]',
            platform='android',
        )
        notification = Notification.objects.create(
            user=user,
            message='Your order has been updated.',
            notification_type='order_update',
        )
        response = Mock()
        response.json.return_value = {'data': [{'status': 'ok', 'id': 'ticket-id'}]}

        with patch('notifications.push.requests.post', return_value=response) as post:
            send_notification_push(notification.id)

        response.raise_for_status.assert_called_once_with()
        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], EXPO_PUSH_URL)
        payload = post.call_args.kwargs['json'][0]
        self.assertEqual(payload['to'], device.token)
        self.assertEqual(payload['body'], notification.message)
        self.assertEqual(payload['data']['notification_id'], notification.id)

    def test_unregistered_device_is_deactivated(self):
        user = User.objects.create_user(username='stale-recipient', password='password')
        device = PushDevice.objects.create(
            user=user,
            token='ExpoPushToken[stale_device_123]',
            platform='android',
        )
        response = Mock()
        response.json.return_value = {
            'data': [{
                'status': 'error',
                'message': 'The recipient is not registered with Expo.',
                'details': {'error': 'DeviceNotRegistered'},
            }]
        }

        with patch('notifications.push.requests.post', return_value=response):
            send_notification_push(
                Notification.objects.create(user=user, message='Update').id
            )

        device.refresh_from_db()
        self.assertFalse(device.is_active)
