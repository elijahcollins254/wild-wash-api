from datetime import datetime, timedelta
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Subscription
from .serializers import SubscriptionSerializer

class SubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def calculate_next_pickup_date(self, frequency):
        today = datetime.now().date()
        if frequency == 'weekly':
            return today + timedelta(days=7)
        elif frequency == 'bi-weekly':
            return today + timedelta(days=14)
        else:  # monthly
            return today + timedelta(days=30)

    def get(self, request):
        try:
            subscription = Subscription.objects.get(user=request.user)
            serializer = SubscriptionSerializer(subscription)
            return Response(serializer.data)
        except Subscription.DoesNotExist:
            return Response(None, status=status.HTTP_200_OK)

    def post(self, request):
        # Cancel existing subscription if any
        Subscription.objects.filter(user=request.user).delete()

        # Create new subscription
        serializer = SubscriptionSerializer(data=request.data)
        if serializer.is_valid():
            next_pickup_date = self.calculate_next_pickup_date(
                serializer.validated_data['frequency']
            )
            subscription = serializer.save(
                user=request.user,
                active=True,
                next_pickup_date=next_pickup_date
            )
            return Response(SubscriptionSerializer(subscription).data, 
                          status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        try:
            subscription = Subscription.objects.get(user=request.user)
            subscription.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Subscription.DoesNotExist:
            return Response(
                {"detail": "No active subscription found."}, 
                status=status.HTTP_404_NOT_FOUND
            )