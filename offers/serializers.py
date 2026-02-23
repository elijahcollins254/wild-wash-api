from rest_framework import serializers
from .models import Offer, UserOffer, OfferNotificationSubscription

class OfferSerializer(serializers.ModelSerializer):
    is_claimed = serializers.SerializerMethodField()
    
    class Meta:
        model = Offer
        fields = [
            'id', 'title', 'description', 'discount_percent', 
            'discount_amount', 'code', 'valid_from', 'valid_until', 
            'is_active', 'max_uses', 'current_uses', 'is_claimed'
        ]
    
    def get_is_claimed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return UserOffer.objects.filter(
                user=request.user, 
                offer=obj
            ).exists()
        return False

class UserOfferSerializer(serializers.ModelSerializer):
    offer = OfferSerializer(read_only=True)
    
    class Meta:
        model = UserOffer
        fields = ['id', 'offer', 'claimed_at', 'used_at', 'is_used']
        read_only_fields = ['user', 'claimed_at', 'used_at', 'is_used']


class OfferNotificationSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferNotificationSubscription
        fields = ['id', 'user', 'phone_number', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']