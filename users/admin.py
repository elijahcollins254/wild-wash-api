from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Avg, Count, Q
from django.utils import timezone

from .models import DataDeletionRequest, Location, PartnerApplication
from .partner_applications import approve_partner_application

User = get_user_model()


@admin.action(description="Activate selected partner accounts")
def activate_selected_partners(modeladmin, request, queryset):
    partners = queryset.filter(Q(role="washer") | Q(staff_type="washer"))
    updated = partners.update(is_active=True)
    modeladmin.message_user(request, f"Activated {updated} partner account(s).", messages.SUCCESS)


@admin.action(description="Disable selected partner accounts")
def disable_selected_partners(modeladmin, request, queryset):
    partners = queryset.filter(Q(role="washer") | Q(staff_type="washer"))
    updated = partners.update(is_active=False)
    modeladmin.message_user(request, f"Disabled {updated} partner account(s).", messages.SUCCESS)


class PartnerAccountActiveFilter(admin.SimpleListFilter):
    title = "partner account status"
    parameter_name = "partner_account_active"

    def lookups(self, request, model_admin):
        return (("active", "Active"), ("disabled", "Disabled"))

    def queryset(self, request, queryset):
        if self.value() == "active":
            return queryset.filter(user__is_active=True)
        if self.value() == "disabled":
            return queryset.filter(user__is_active=False)
        return queryset


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'region', 'is_active', 'created_at')
    search_fields = ('name', 'region', 'description')
    list_filter = ('region', 'is_active')

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("id", "username", "email", "phone", "role", "business_name", "service_location", "is_staff", "is_location_admin", "is_active")
    list_filter = ("role", "staff_type", "service_location", "is_staff", "is_location_admin", "is_active")
    search_fields = ("username", "email", "phone")
    ordering = ("id",)
    actions = (activate_selected_partners, disable_selected_partners)

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


@admin.register(PartnerApplication)
class PartnerApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "business_name",
        "applicant_name",
        "username",
        "location",
        "status",
        "active_orders",
        "average_rating",
        "rating_count",
        "account_is_active",
        "created_at",
    )
    list_filter = ("status", "business_type", PartnerAccountActiveFilter, "created_at")
    search_fields = (
        "business_name",
        "first_name",
        "last_name",
        "user__username",
        "email",
        "phone",
        "location",
    )
    readonly_fields = (
        "user",
        "status",
        "reviewed_by",
        "reviewed_at",
        "created_at",
        "updated_at",
        "active_orders",
        "completed_orders",
        "average_rating",
        "rating_count",
        "account_is_active",
    )
    list_select_related = ("user", "reviewed_by")
    actions = ("approve_partner_applications", "reject_partner_applications")

    fieldsets = (
        ("Applicant", {"fields": ("user", "first_name", "last_name", "phone", "email")}),
        ("Business", {"fields": ("business_name", "business_type", "location", "pickup_address", "service_area", "machine_count", "pickup_latitude", "pickup_longitude")}),
        ("Review", {"fields": ("status", "reviewer_notes", "reviewed_by", "reviewed_at")}),
        ("Partner activity", {"fields": ("active_orders", "completed_orders", "average_rating", "rating_count", "account_is_active")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            active_order_count=Count(
                "user__washed_orders",
                filter=~Q(user__washed_orders__status__in=["delivered", "cancelled"]),
                distinct=True,
            ),
            completed_order_count=Count(
                "user__washed_orders",
                filter=Q(user__washed_orders__status="delivered"),
                distinct=True,
            ),
            average_rating_value=Avg("user__washed_orders__review__rating"),
            rating_count_value=Count("user__washed_orders__review", distinct=True),
        )

    @admin.display(description="Applicant", ordering="first_name")
    def applicant_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

    @admin.display(description="Username", ordering="user__username")
    def username(self, obj):
        return obj.user.username

    @admin.display(description="Active orders", ordering="active_order_count")
    def active_orders(self, obj):
        return obj.active_order_count

    @admin.display(description="Completed orders", ordering="completed_order_count")
    def completed_orders(self, obj):
        return obj.completed_order_count

    @admin.display(description="Average rating", ordering="average_rating_value")
    def average_rating(self, obj):
        return obj.average_rating_value

    @admin.display(description="Ratings", ordering="rating_count_value")
    def rating_count(self, obj):
        return obj.rating_count_value

    @admin.display(boolean=True, description="Account active", ordering="user__is_active")
    def account_is_active(self, obj):
        return obj.user.is_active

    @admin.action(description="Approve selected partner applications")
    def approve_partner_applications(self, request, queryset):
        approved = 0
        skipped = 0
        for application in queryset.filter(status="pending").select_related("user"):
            try:
                approve_partner_application(application, request.user)
                approved += 1
            except ValidationError:
                skipped += 1

        if approved:
            self.message_user(request, f"Approved {approved} partner application(s).", messages.SUCCESS)
        if skipped:
            self.message_user(request, f"Skipped {skipped} application(s) that were already reviewed.", messages.WARNING)

    @admin.action(description="Reject selected partner applications")
    def reject_partner_applications(self, request, queryset):
        updated = queryset.filter(status="pending").update(
            status="rejected",
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
            reviewer_notes="Rejected from Django admin.",
            updated_at=timezone.now(),
        )
        self.message_user(request, f"Rejected {updated} partner application(s).", messages.SUCCESS)


@admin.register(DataDeletionRequest)
class DataDeletionRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'request_type', 'account_email', 'account_phone', 'status', 'created_at')
    list_filter = ('request_type', 'status', 'created_at')
    search_fields = ('account_email', 'account_phone', 'details')
    readonly_fields = ('user', 'account_email', 'account_phone', 'request_type', 'details', 'created_at')
    fields = ('user', 'account_email', 'account_phone', 'request_type', 'details', 'status', 'review_notes', 'created_at', 'updated_at')
