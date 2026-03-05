# users/serializers.py
from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Location, ActivityLog

User = get_user_model()

class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'name', 'description', 'is_active', 'created_at']

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

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "phone",
            "role",
            "location",
            "pickup_address",
            "is_staff",
            "service_location",
            "service_location_display",
            "date_joined",
            "created_at",
        ]
        read_only_fields = ["id", "is_staff", "date_joined"]

    def get_service_location_display(self, obj):
        if obj.service_location:
            return obj.service_location.name
        return None
    
    def get_created_at(self, obj):
        """Return date_joined as created_at for frontend compatibility"""
        return obj.date_joined


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