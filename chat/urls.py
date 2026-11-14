from django.urls import path

from .views import (
    MarkSupportMessagesReadView,
    SupportChatEventsView,
    SupportChatUnreadCountView,
    SupportChatView,
)

urlpatterns = [
    path('events/', SupportChatEventsView.as_view(), name='support-chat-events'),
    path('read/', MarkSupportMessagesReadView.as_view(), name='support-chat-read'),
    path('unread-count/', SupportChatUnreadCountView.as_view(), name='support-chat-unread-count'),
    path('', SupportChatView.as_view(), name='support-chat'),
]
