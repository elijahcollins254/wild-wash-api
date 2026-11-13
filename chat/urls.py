from django.urls import path

from .views import SupportChatView

urlpatterns = [
    path('', SupportChatView.as_view(), name='support-chat'),
]
