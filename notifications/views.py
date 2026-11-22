# notifications/views.py
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification, PushDevice
from .serializers import NotificationSerializer, PushDeviceSerializer


class PushDeviceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PushDeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device, created = PushDevice.objects.update_or_create(
            token=serializer.validated_data['token'],
            defaults={
                'user': request.user,
                'platform': serializer.validated_data['platform'],
                'is_active': True,
            },
        )
        return Response(
            {'status': 'registered', 'id': device.id},
            status=201 if created else 200,
        )

    def delete(self, request):
        serializer = PushDeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        PushDevice.objects.filter(
            user=request.user,
            token=serializer.validated_data['token'],
        ).update(is_active=False)
        return Response({'status': 'unregistered'})


class NotificationViewSet(viewsets.ModelViewSet):
    """Simple notification list for users. Create notifications via signals/tasks."""
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # only return notifications for the authenticated user
        # Use select_related to avoid N+1 queries
        return Notification.objects.filter(user=self.request.user).select_related('user', 'order').order_by('-created_at')

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a notification as read."""
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response({"status": "ok", "id": notification.id})
