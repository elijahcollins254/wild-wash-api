import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .events import serialize_support_message, support_customer_group
from .models import SupportMessage

logger = logging.getLogger(__name__)


@receiver(post_save, sender=SupportMessage)
def publish_support_message(sender, instance, created, **kwargs):
    if not created or not instance.is_from_support:
        return

    message_data = serialize_support_message(instance)
    group_name = support_customer_group(instance.conversation.customer_id)

    def publish():
        channel_layer = get_channel_layer()
        if channel_layer is None:
            logger.error('Cannot publish support message: no channel layer is configured.')
            return
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'support.message',
                'message': message_data,
            },
        )

    transaction.on_commit(publish)
