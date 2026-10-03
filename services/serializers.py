# services/serializers.py
from rest_framework import serializers
from .models import Service


class ServiceSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    category = serializers.CharField(source='category.slug', read_only=True, allow_null=True)

    def get_image_url(self, obj):
        """Return only the admin-configured URL; clients choose their own fallback."""
        return obj.image_link or None

    class Meta:
        model = Service
        fields = ["id", "name", "category", "price", "description", "image", "image_url"]
        read_only_fields = ["id"]
