from django.conf import settings
from django.core.checks import Warning, register


@register()
def check_support_chat_channel_layer(app_configs, **kwargs):
    if settings.CHANNEL_REDIS_URL:
        return []
    return [
        Warning(
            'Support chat is using an in-memory channel layer.',
            hint='Set CHANNEL_REDIS_URL to a shared Redis service for production or multi-process deployments.',
            id='chat.W001',
        ),
    ]
