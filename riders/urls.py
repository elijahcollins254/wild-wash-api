# riders/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AdminRiderWalletCreditView,
    AdminRiderWalletsView,
    AdminWasherWalletCreditView,
    AdminWasherWalletsView,
    MpesaB2CResultView,
    MpesaB2CTimeoutView,
    RiderLocationViewSet,
    PublicRiderLocationsView,
    RiderProfileViewSet,
    RiderWalletView,
    WasherWalletView,
)

router = DefaultRouter()
# authenticated CRUD for locations (used by rider device / admin)
router.register(r'locations', RiderLocationViewSet, basename='rider-location')
# profiles (public read, admin write)
router.register(r'profiles', RiderProfileViewSet, basename='rider-profile')

urlpatterns = [
    path("wallet/me/", RiderWalletView.as_view(), name="rider-wallet-me"),
    path("washer-wallet/me/", WasherWalletView.as_view(), name="washer-wallet-me"),
    path("wallets/", AdminRiderWalletsView.as_view(), name="admin-rider-wallets"),
    path("wallets/<int:rider_id>/credit/", AdminRiderWalletCreditView.as_view(), name="admin-rider-wallet-credit"),
    path("washer-wallets/", AdminWasherWalletsView.as_view(), name="admin-washer-wallets"),
    path("washer-wallets/<int:washer_id>/credit/", AdminWasherWalletCreditView.as_view(), name="admin-washer-wallet-credit"),
    path("mpesa/b2c/result/", MpesaB2CResultView.as_view(), name="rider-b2c-result"),
    path("mpesa/b2c/timeout/", MpesaB2CTimeoutView.as_view(), name="rider-b2c-timeout"),
    # public latest locations: GET /riders/
    path("", PublicRiderLocationsView.as_view(), name="rider-latest"),
    # include viewset routes at /riders/
    path("", include(router.urls)),
]
