from django.conf import settings
from django.db import models
from django.utils import timezone


class SupportConversation(models.Model):
    customer = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='support_conversation',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ('-updated_at',)

    def __str__(self):
        return f'Support conversation with {self.customer}'


class SupportMessage(models.Model):
    conversation = models.ForeignKey(
        SupportConversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='support_messages_sent',
    )
    is_from_support = models.BooleanField(default=False)
    body = models.CharField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'id')
        indexes = [
            models.Index(
                fields=('conversation', 'created_at'),
                name='chat_msg_conv_created_idx',
            ),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        SupportConversation.objects.filter(pk=self.conversation_id).update(
            updated_at=timezone.now(),
        )

    def __str__(self):
        return f'Message in conversation {self.conversation_id}'
