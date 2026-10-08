from django.contrib import admin
from .models import RiderProfile, RiderLocation, RiderWallet, RiderWalletTransaction

@admin.register(RiderProfile)
class RiderProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "display_name", "phone", "vehicle_type", "vehicle_reg", "is_active")
    search_fields = ("display_name", "user__username", "phone", "vehicle_reg")
    list_filter = ("vehicle_type", "is_active")
    readonly_fields = ("created_at", "updated_at")

@admin.register(RiderLocation)
class RiderLocationAdmin(admin.ModelAdmin):
    list_display = ("id", "rider", "latitude", "longitude", "recorded_at")
    search_fields = ("rider__username",)
    list_filter = ("recorded_at",)
    readonly_fields = ("created_at",)
    ordering = ("-recorded_at",)


@admin.register(RiderWallet)
class RiderWalletAdmin(admin.ModelAdmin):
    list_display = ("id", "rider", "balance", "payout_phone", "updated_at")
    search_fields = ("rider__username", "rider__phone", "payout_phone")
    readonly_fields = ("rider", "balance", "payout_phone", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RiderWalletTransaction)
class RiderWalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "wallet", "transaction_type", "status", "amount", "created_by", "created_at")
    list_filter = ("transaction_type", "status", "created_at")
    search_fields = ("wallet__rider__username", "reference", "provider_transaction_id")
    readonly_fields = (
        "wallet", "transaction_type", "status", "amount", "balance_after", "reference",
        "reason", "payout_phone", "created_by", "conversation_id", "originator_conversation_id",
        "provider_transaction_id", "provider_payload", "created_at", "updated_at",
    )
    actions = None
