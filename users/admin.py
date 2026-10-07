from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from .models import DataDeletionRequest, Location

User = get_user_model()

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'region', 'is_active', 'created_at')
    search_fields = ('name', 'region', 'description')
    list_filter = ('region', 'is_active')

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("id", "username", "email", "phone", "role", "service_location", "is_staff", "is_location_admin", "is_active")
    list_filter = ("role", "service_location", "is_staff", "is_location_admin", "is_active")
    search_fields = ("username", "email", "phone")
    ordering = ("id",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email", "phone")}),
        ("Role & Location", {"fields": ("role", "service_location", "is_location_admin")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "username", "email", "phone", "role", 
                "service_location", "is_location_admin",
                "password1", "password2", "is_staff", "is_active"
            ),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if request.user.is_staff and request.user.service_location:
            return qs.filter(service_location=request.user.service_location)
        return qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "service_location" and not request.user.is_superuser:
            kwargs["queryset"] = Location.objects.filter(id=request.user.service_location_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(DataDeletionRequest)
class DataDeletionRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'request_type', 'account_email', 'account_phone', 'status', 'created_at')
    list_filter = ('request_type', 'status', 'created_at')
    search_fields = ('account_email', 'account_phone', 'details')
    readonly_fields = ('user', 'account_email', 'account_phone', 'request_type', 'details', 'created_at')
    fields = ('user', 'account_email', 'account_phone', 'request_type', 'details', 'status', 'review_notes', 'created_at', 'updated_at')
