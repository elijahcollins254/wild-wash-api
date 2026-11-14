from django.db.models import Count, Max, Q
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from channels.layers import get_channel_layer

from .events import support_message_stream
from .models import SupportConversation, SupportMessage
from .serializers import (
    CreateSupportMessageSerializer,
    MarkSupportMessagesReadSerializer,
    SupportMessageSerializer,
)


class SupportChatView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        conversation, _ = SupportConversation.objects.get_or_create(
            customer=request.user,
        )
        messages = list(
            conversation.messages.select_related('sender').all()
        )
        latest_message_id = max((message.id for message in messages), default=0)
        conversation.messages.filter(
            is_from_support=True,
            customer_read_at__isnull=True,
            id__lte=latest_message_id,
        ).update(customer_read_at=timezone.now())
        return Response(SupportMessageSerializer(messages, many=True).data)

    def post(self, request):
        serializer = CreateSupportMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        conversation, _ = SupportConversation.objects.get_or_create(
            customer=request.user,
        )
        message = SupportMessage.objects.create(
            conversation=conversation,
            sender=request.user,
            body=serializer.validated_data['body'],
        )
        return Response(
            SupportMessageSerializer(message).data,
            status=status.HTTP_201_CREATED,
        )


class SupportChatEventsView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        raw_last_event_id = request.headers.get('Last-Event-ID', '0')
        try:
            last_event_id = int(raw_last_event_id)
        except (TypeError, ValueError) as error:
            raise ValidationError({'Last-Event-ID': 'Must be a non-negative integer.'}) from error
        if last_event_id < 0:
            raise ValidationError({'Last-Event-ID': 'Must be a non-negative integer.'})

        if get_channel_layer() is None:
            return Response(
                {'detail': 'Support events are temporarily unavailable.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        response = StreamingHttpResponse(
            support_message_stream(request.user.pk, last_event_id),
            content_type='text/event-stream',
        )
        response['Cache-Control'] = 'no-cache, no-transform'
        response['X-Accel-Buffering'] = 'no'
        return response


class MarkSupportMessagesReadView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        serializer = MarkSupportMessagesReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation = SupportConversation.objects.filter(
            customer=request.user,
        ).first()
        if conversation:
            conversation.messages.filter(
                is_from_support=True,
                customer_read_at__isnull=True,
                id__lte=serializer.validated_data['through_id'],
            ).update(customer_read_at=timezone.now())
        return Response(status=status.HTTP_204_NO_CONTENT)


class SupportChatUnreadCountView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        conversation = SupportConversation.objects.filter(
            customer=request.user,
        ).first()
        if not conversation:
            return Response({'unread_count': 0, 'last_message_id': 0})

        counts = conversation.messages.aggregate(
            unread_count=Count(
                'id',
                filter=Q(is_from_support=True, customer_read_at__isnull=True),
            ),
            last_message_id=Max(
                'id',
                filter=Q(is_from_support=True),
            ),
        )
        return Response({
            'unread_count': counts['unread_count'],
            'last_message_id': counts['last_message_id'] or 0,
        })
