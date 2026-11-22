import logging

import requests

from .models import Notification, PushDevice

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send'
EXPO_PUSH_BATCH_SIZE = 100


def send_notification_push(notification_id):
    notification = (
        Notification.objects
        .select_related('order')
        .filter(pk=notification_id)
        .first()
    )
    if notification is None:
        logger.warning('Cannot send push for missing notification %s.', notification_id)
        return

    devices = list(PushDevice.objects.filter(user=notification.user, is_active=True))
    if not devices:
        return

    data = {
        'notification_id': notification.id,
        'notification_type': notification.notification_type,
    }
    if notification.order_id:
        data['order_code'] = notification.order.code

    messages = [
        {
            'to': device.token,
            'title': 'Wild Wash',
            'body': notification.message,
            'sound': 'default',
            'channelId': 'default',
            'data': data,
        }
        for device in devices
    ]

    for offset in range(0, len(messages), EXPO_PUSH_BATCH_SIZE):
        batch_devices = devices[offset:offset + EXPO_PUSH_BATCH_SIZE]
        batch = messages[offset:offset + EXPO_PUSH_BATCH_SIZE]
        try:
            response = requests.post(
                EXPO_PUSH_URL,
                json=batch,
                headers={'Accept': 'application/json', 'Content-Type': 'application/json'},
                timeout=(3, 10),
            )
            response.raise_for_status()
            tickets = response.json().get('data', [])
        except (requests.RequestException, ValueError, AttributeError):
            logger.exception(
                'Failed to send Expo push notifications for notification %s.',
                notification_id,
            )
            continue

        if not isinstance(tickets, list):
            logger.error('Expo returned an invalid ticket response for notification %s.', notification_id)
            continue

        for device, ticket in zip(batch_devices, tickets):
            if not isinstance(ticket, dict) or ticket.get('status') != 'error':
                continue
            details = ticket.get('details') or {}
            if details.get('error') == 'DeviceNotRegistered':
                device.is_active = False
                device.save(update_fields=['is_active'])
            logger.warning(
                'Expo rejected push for device %s: %s',
                device.pk,
                ticket.get('message', 'unknown error'),
            )
