from rest_framework import serializers

from .models import SupportMessage


class SupportMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportMessage
        fields = ('id', 'body', 'is_from_support', 'created_at')
        read_only_fields = fields


class CreateSupportMessageSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=4000, trim_whitespace=True)


class MarkSupportMessagesReadSerializer(serializers.Serializer):
    through_id = serializers.IntegerField(min_value=0)
