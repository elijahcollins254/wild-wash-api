from django.urls import path

from .views import SupportChatUnreadCountView, SupportChatView

urlpatterns = [
    path('unread-count/', SupportChatUnreadCountView.as_view(), name='support-chat-unread-count'),
    path('', SupportChatView.as_view(), name='support-chat'),
]
