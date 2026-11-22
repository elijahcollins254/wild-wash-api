# -------------------------
# notifications/urls.py
# -------------------------
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet, PushDeviceView

router = DefaultRouter()
router.register(r'', NotificationViewSet, basename='notification')

urlpatterns = [
    path('devices/', PushDeviceView.as_view(), name='push-device'),
    path('', include(router.urls)),
]
