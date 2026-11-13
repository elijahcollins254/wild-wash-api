from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SupportConversation, SupportMessage
from .serializers import CreateSupportMessageSerializer, SupportMessageSerializer


class SupportChatView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        conversation, _ = SupportConversation.objects.get_or_create(
            customer=request.user,
        )
        messages = conversation.messages.select_related('sender').all()
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
