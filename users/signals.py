import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .events import USER_COUNT_GROUP


logger = logging.getLogger(__name__)


def _publish_user_count(user_model):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.error('Cannot publish updated user count because no channel layer is configured.')
        return

    async_to_sync(channel_layer.group_send)(
        USER_COUNT_GROUP,
        {
            'type': 'users.count_changed',
            'user_count': user_model.objects.count(),
        },
    )


@receiver(post_save, sender=get_user_model(), dispatch_uid='users.publish_count_on_create')
def publish_user_count_on_create(sender, created, **kwargs):
    if created:
        transaction.on_commit(lambda: _publish_user_count(sender), robust=True)


@receiver(post_delete, sender=get_user_model(), dispatch_uid='users.publish_count_on_delete')
def publish_user_count_on_delete(sender, **kwargs):
    transaction.on_commit(lambda: _publish_user_count(sender), robust=True)
