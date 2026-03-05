# urls for Wild Wash Django apps
# -------------------------
# users/urls.py
# -------------------------
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, LoginView, ChangePasswordView, 
    get_csrf, RegisterView, UserProfileView,
    LocationViewSet, StaffViewSet, StaffLoginView, AdminLoginView,
    RequestPasswordResetView, VerifyPasswordResetCodeView, ConfirmPasswordResetView,
    ActivityLogViewSet
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'locations', LocationViewSet, basename='location')
router.register(r'staff', StaffViewSet, basename='staff')

urlpatterns = [
    path('me/', UserProfileView.as_view(), name='user-profile'),
    path('', include(router.urls)),
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('staff/login/', StaffLoginView.as_view(), name='staff-login'),
    path('admin/login/', AdminLoginView.as_view(), name='admin-login'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('csrf/', get_csrf, name='csrf'),
    path('password-reset/request/', RequestPasswordResetView.as_view(), name='password-reset-request'),
    path('password-reset/verify/', VerifyPasswordResetCodeView.as_view(), name='password-reset-verify'),
    path('password-reset/confirm/', ConfirmPasswordResetView.as_view(), name='password-reset-confirm'),
    path('users/<int:user_id>/activity-logs/', ActivityLogViewSet.as_view({'get': 'list'}), name='user-activity-logs'),
]


