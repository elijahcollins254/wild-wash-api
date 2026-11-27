# users/serializers.py
import re

from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import DataDeletionRequest, Location, ActivityLog, PartnerApplication, format_phone_number

User = get_user_model()


def _validate_unique_phone(value, instance=None):
    normalized_phone = format_phone_number(value)
    if normalized_phone:
        users_with_phone = User.objects.filter(phone=normalized_phone)
        if instance is not None:
            users_with_phone = users_with_phone.exclude(pk=instance.pk)
        if users_with_phone.exists():
            raise serializers.ValidationError(
                "This phone number is already assigned to another user."
            )
    return normalized_phone


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'name', 'region', 'description', 'is_active', 'created_at']

class StaffCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    location = serializers.CharField(required=False, allow_blank=True, max_length=100, write_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'password', 
            'first_name', 'last_name', 
            'service_location', 'location', 'is_location_admin'
        ]
    
    def validate_username(self, value):
        """Check if username already exists"""
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                f"A user with the username '{value}' already exists. Please choose a different username."
            )
        return value
    
    def validate_email(self, value):
        """Check if email already exists"""
        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                f"A user with the email '{value}' already exists. Please use a different email address."
            )
        return value
        
    def create(self, validated_data):
        password = validated_data.pop('password')
        location_name = validated_data.pop('location', '').strip()
        
        user = User.objects.create(
            is_staff=True,
            **validated_data
        )
        user.set_password(password)
        
        # If location text is provided but service_location isn't set, try to match it
        if location_name and not user.service_location:
            location_obj = Location.objects.filter(
                name__iexact=location_name,
                is_active=True
            ).first()
            
            if not location_obj:
                location_obj = Location.objects.filter(
                    name__icontains=location_name,
                    is_active=True
                ).first()
            
            if location_obj:
                user.service_location = location_obj
        
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    service_location_display = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    phone = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "phone",
            "role",
            "staff_type",
            "location",
            "pickup_address",
            "pickup_latitude",
            "pickup_longitude",
            "machine_count",
            "business_name",
            "business_type",
            "service_area",
            "email",
            "is_staff",
            "is_active",
            "service_location",
            "service_location_display",
            "date_joined",
            "created_at",
            "profile_complete",
        ]
        read_only_fields = ["id", "is_staff", "date_joined"]

    def get_service_location_display(self, obj):
        if obj.service_location:
            return obj.service_location.name
        return None
    
    def get_created_at(self, obj):
        """Return date_joined as created_at for frontend compatibility"""
        return obj.date_joined

    def validate_phone(self, value):
        return _validate_unique_phone(value, self.instance)


class PartnerApplicationSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    active_order_count = serializers.SerializerMethodField()
    completed_order_count = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    account_is_active = serializers.BooleanField(source="user.is_active", read_only=True)

    class Meta:
        model = PartnerApplication
        fields = [
            "id",
            "user",
            "username",
            "account_is_active",
            "first_name",
            "last_name",
            "phone",
            "email",
            "business_name",
            "business_type",
            "location",
            "pickup_address",
            "service_area",
            "machine_count",
            "pickup_latitude",
            "pickup_longitude",
            "status",
            "active_order_count",
            "completed_order_count",
            "average_rating",
            "rating_count",
            "reviewer_notes",
            "reviewed_at",
            "created_at",
        ]
        read_only_fields = ["id", "user", "username", "status", "reviewer_notes", "reviewed_at", "created_at"]

    def get_active_order_count(self, obj):
        return getattr(obj, "active_order_count", 0)

    def get_completed_order_count(self, obj):
        return getattr(obj, "completed_order_count", 0)

    def get_average_rating(self, obj):
        return getattr(obj, "average_rating", None)

    def get_rating_count(self, obj):
        return getattr(obj, "rating_count", 0)

    def validate(self, attrs):
        user = self.context["request"].user
        if PartnerApplication.objects.filter(user=user, status__in=["pending", "approved"]).exists():
            raise serializers.ValidationError(
                "You already have a pending or approved partner application."
            )
        return attrs

    def validate_phone(self, value):
        return _validate_unique_phone(value, self.context["request"].user)

    def validate_machine_count(self, value):
        if value < 1:
            raise serializers.ValidationError("At least one washing machine is required.")
        return value

    def validate_pickup_latitude(self, value):
        if value is not None and not -90 <= value <= 90:
            raise serializers.ValidationError("Latitude must be between -90 and 90.")
        return value

    def validate_pickup_longitude(self, value):
        if value is not None and not -180 <= value <= 180:
            raise serializers.ValidationError("Longitude must be between -180 and 180.")
        return value

    def create(self, validated_data):
        return PartnerApplication.objects.create(
            user=self.context["request"].user,
            **validated_data,
        )


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    location = serializers.CharField(required=False, allow_blank=True, max_length=100)

    class Meta:
        model = User
        fields = ["id", "username", "phone", "password", "first_name", "last_name", "location", "pickup_address"]

    def validate_username(self, value):
        """Check if username already exists"""
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                f"A user with the username '{value}' already exists. Please choose a different username."
            )
        return value

    def validate_phone(self, value):
        digits = re.sub(r"\D", "", value)
        if not re.fullmatch(r"(?:0[17]\d{8}|254[17]\d{8})", digits):
            raise serializers.ValidationError("Please enter a valid Kenya phone number.")
        return _validate_unique_phone(value)

    def create(self, validated_data):
        password = validated_data.pop("password")
        location_name = validated_data.get("location", "").strip()
        
        user = User(**validated_data)
        user.set_password(password)
        
        # If location is provided, try to match it with a Location object
        if location_name:
            # Try exact match first
            location_obj = Location.objects.filter(
                name__iexact=location_name,
                is_active=True
            ).first()
            
            # If no exact match, try case-insensitive contains
            if not location_obj:
                location_obj = Location.objects.filter(
                    name__icontains=location_name,
                    is_active=True
                ).first()
            
            # Set as service_location if found (useful for riders/staff later)
            if location_obj:
                user.service_location = location_obj
        
        user.save()
        return user


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=6)

class ActivityLogSerializer(serializers.ModelSerializer):
    admin_username = serializers.CharField(source='admin_user.username', read_only=True)
    
    class Meta:
        model = ActivityLog
        fields = [
            'id', 'user', 'action', 'description', 'ip_address', 'user_agent',
            'admin_user', 'admin_username', 'timestamp', 'changes'
        ]
        read_only_fields = ['id', 'timestamp', 'admin_user']


class DataDeletionRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataDeletionRequest
        fields = ['id', 'request_type', 'details', 'status', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']

    def validate(self, attrs):
        if attrs.get('request_type') == 'data' and not attrs.get('details', '').strip():
            raise serializers.ValidationError({
                'details': 'Describe which personal data you want deleted.'
            })
        return attrs