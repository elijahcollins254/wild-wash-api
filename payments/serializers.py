# payments/serializers.py
from rest_framework import serializers
from .models import Payment, MpesaSTKRequest, BNPLUser
from .models import TradeIn
from django.contrib.auth import get_user_model

User = get_user_model()


class PaymentSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    # If you use order FK, you can replace order_id with a nested serializer or PrimaryKeyRelatedField

    class Meta:
        model = Payment
        fields = [
            "id",
            "user",
            "order_id",
            "provider",
            "provider_reference",
            "amount",
            "currency",
            "phone_number",
            "status",
            "initiated_at",
            "completed_at",
            "raw_payload",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "initiated_at", "completed_at", "created_at", "updated_at"]


class PaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["order_id", "amount", "currency", "phone_number", "provider"]

    def create(self, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        payment = Payment.objects.create(user=user, **validated_data)
        return payment


class BNPLUserSerializer(serializers.ModelSerializer):
    is_enrolled = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    user_phone = serializers.SerializerMethodField()

    class Meta:
        model = BNPLUser
        fields = [
            'id',
            'user',
            'user_name',
            'user_phone',
            'is_enrolled',
            'is_active',
            'phone_number',
            'credit_limit',
            'current_balance',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'user', 'credit_limit', 'current_balance', 'created_at', 'updated_at', 'is_enrolled']

    def get_is_enrolled(self, obj):
        """Return True if user is enrolled AND active in BNPL"""
        return obj.is_active

    def get_user_name(self, obj):
        """Return user's full name or username"""
        if obj.user.first_name and obj.user.last_name:
            return f"{obj.user.first_name} {obj.user.last_name}"
        return obj.user.username

    def get_user_phone(self, obj):
        """Return user's phone number"""
        return obj.user.phone


class MpesaSTKRequestSerializer(serializers.ModelSerializer):
    payment = PaymentSerializer(read_only=True)
    payment_id = serializers.PrimaryKeyRelatedField(
        queryset=Payment.objects.all(), source="payment", write_only=True
    )

    class Meta:
        model = MpesaSTKRequest
        fields = [
            "id",
            "payment",
            "payment_id",
            "checkout_request_id",
            "merchant_request_id",
            "result_code",
            "result_desc",
            "callback_payload",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "payment", "created_at", "updated_at"]


class TradeInSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = TradeIn
        fields = [
            'id',
            'user',
            'description',
            'estimated_price',
            'contact_phone',
            'status',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'user', 'status', 'created_at', 'updated_at']
