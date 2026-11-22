from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Notification


@receiver(post_save, sender=Notification)
def send_push_after_notification_created(sender, instance, created, raw=False, **kwargs):
    if not created or raw:
        return

    notification_id = instance.pk

    def dispatch_push():
        from .push import send_notification_push

        send_notification_push(notification_id)

    transaction.on_commit(dispatch_push)
