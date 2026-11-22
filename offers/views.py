from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from django.utils import timezone
from django.db import models
from django.http import JsonResponse
from .models import Offer, UserOffer, OfferNotificationSubscription, Banner
from .serializers import OfferSerializer, UserOfferSerializer, OfferNotificationSubscriptionSerializer, BannerSerializer


class BannerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BannerSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        now = timezone.now()
        return Banner.objects.filter(
            is_active=True,
            valid_from__lte=now,
        ).filter(
            models.Q(valid_until__isnull=True) | models.Q(valid_until__gt=now)
        ).order_by('sort_order', '-created_at')

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


class OfferSubscriptionViewSet(viewsets.ViewSet):
    """
    Endpoint to manage offer notification subscriptions.
    Users can subscribe/unsubscribe to receive SMS notifications about new offers.
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get', 'post'], permission_classes=[IsAuthenticated])
    def my_subscription(self, request):
        """
        GET: Get the current user's subscription status
        POST: Create or update the current user's subscription
        """
        if request.method == 'GET':
            subscription = OfferNotificationSubscription.objects.filter(user=request.user).first()
            if subscription:
                serializer = OfferNotificationSubscriptionSerializer(subscription)
                return Response(serializer.data)
            return Response({'is_subscribed': False})

        elif request.method == 'POST':
            phone_number = request.user.phone or None
            conflict = Response(
                {'detail': 'This phone number is already linked to another offer subscription.'},
                status=status.HTTP_409_CONFLICT,
            )

            with transaction.atomic():
                subscription = OfferNotificationSubscription.objects.select_for_update().filter(
                    user=request.user,
                ).first()
                created = False

                if subscription is None:
                    if phone_number:
                        subscription, created = OfferNotificationSubscription.objects.get_or_create(
                            phone_number=phone_number,
                            defaults={'user': request.user},
                        )
                        if subscription.user_id not in (None, request.user.pk):
                            return conflict
                        if subscription.user_id is None:
                            subscription.user = request.user
                    else:
                        subscription, created = OfferNotificationSubscription.objects.get_or_create(
                            user=request.user,
                            defaults={'phone_number': None},
                        )
                elif phone_number and subscription.phone_number != phone_number:
                    matching_subscription = OfferNotificationSubscription.objects.select_for_update().filter(
                        phone_number=phone_number,
                    ).exclude(pk=subscription.pk).first()
                    if matching_subscription:
                        if matching_subscription.user_id is not None:
                            return conflict
                        matching_subscription.delete()
                    subscription.phone_number = phone_number

                subscription.is_active = True
                subscription.save()

            serializer = OfferNotificationSubscriptionSerializer(subscription)
            return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def unsubscribe(self, request):
        """
        Unsubscribe from offer notifications
        """
        subscription = OfferNotificationSubscription.objects.filter(user=request.user).first()
        if subscription:
            subscription.is_active = False
            subscription.save()
            return Response({'detail': 'Unsubscribed from offer notifications'}, status=status.HTTP_200_OK)
        return Response({'detail': 'Not subscribed'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def subscribed_numbers(self, request):
        """
        Get all active subscribed phone numbers for SMS sending.
        This endpoint is used by external services to fetch the list of numbers to send SMS to.
        CORS enabled for cross-origin requests.
        """
        subscriptions = OfferNotificationSubscription.objects.filter(is_active=True).exclude(
            phone_number__isnull=True
        ).exclude(phone_number='')
        
        # Return only phone numbers as a simple list
        phone_numbers = [sub.phone_number for sub in subscriptions]
        
        response = Response({
            'count': len(phone_numbers),
            'phone_numbers': phone_numbers,
            'timestamp': timezone.now()
        })
        
        # Add CORS headers for cross-origin requests
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type'
        
        return response