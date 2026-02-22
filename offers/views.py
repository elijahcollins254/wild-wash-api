from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.db import models
from .models import Offer, UserOffer
from .serializers import OfferSerializer, UserOfferSerializer

class OfferViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Offer.objects.filter(is_active=True)
    serializer_class = OfferSerializer
    permission_classes = [AllowAny]

    def get_permissions(self):
        """
        Allow anyone to list/retrieve offers, but require authentication for claiming
        """
        if self.action == 'claim':
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        now = timezone.now()
        return Offer.objects.filter(
            is_active=True,
            valid_from__lte=now,
        ).filter(
            models.Q(valid_until__isnull=True) | 
            models.Q(valid_until__gt=now)
        ).filter(
            models.Q(max_uses__isnull=True) |
            models.Q(current_uses__lt=models.F('max_uses'))
        )

    @action(detail=True, methods=['post'])
    def claim(self, request, pk=None):
        offer = self.get_object()
        user = request.user

        # Check if user already claimed this offer
        if UserOffer.objects.filter(user=user, offer=offer).exists():
            return Response(
                {'detail': 'You have already claimed this offer.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if offer is still available
        if offer.max_uses and offer.current_uses >= offer.max_uses:
            return Response(
                {'detail': 'This offer has reached its maximum usage limit.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create user offer and increment usage counter
        user_offer = UserOffer.objects.create(user=user, offer=offer)
        offer.current_uses += 1
        offer.save()

        return Response(
            UserOfferSerializer(user_offer).data,
            status=status.HTTP_201_CREATED
        )

class UserOfferViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserOfferSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserOffer.objects.filter(user=self.request.user)