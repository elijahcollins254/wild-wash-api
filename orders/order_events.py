import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .events import order_event_groups
from .models import Order

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Order)
def publish_order_update(sender, instance, **kwargs):
    groups = order_event_groups(instance)
    order_id = instance.pk

    def publish():
        channel_layer = get_channel_layer()
        if channel_layer is None:
            logger.warning('Cannot publish order update: no channel layer is configured.')
            return

        try:
            for group in groups:
                async_to_sync(channel_layer.group_send)(
                    group,
                    {'type': 'orders.changed', 'order_id': order_id},
                )
        except Exception:
            logger.exception('Failed to publish order update for order %s.', order_id)

    transaction.on_commit(publish)
