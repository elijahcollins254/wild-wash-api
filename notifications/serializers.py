# notifications/serializers.py
from rest_framework import serializers
from django.core.validators import RegexValidator
from .models import Notification


expo_push_token_validator = RegexValidator(
    regex=r'^(Expo|Exponent)PushToken\[[A-Za-z0-9_-]+\]$',
    message='Enter a valid Expo push token.',
)


class PushDeviceSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=255, validators=[expo_push_token_validator])
    platform = serializers.ChoiceField(choices=['android', 'ios'])


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "user", "order", "message", "notification_type", "created_at", "is_read"]
        read_only_fields = ["id", "created_at", "user"]
