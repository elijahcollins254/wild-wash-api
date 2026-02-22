from django.contrib import admin
from django.utils.text import slugify
from .models import ServiceCategory, Service


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "service_count", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "description")
    ordering = ("name",)
    readonly_fields = ("slug", "created_at", "updated_at")
    
    def save_model(self, request, obj, form, change):
        """Auto-generate slug from name if not provided."""
        if not obj.slug:
            obj.slug = slugify(obj.name)
        super().save_model(request, obj, form, change)
    
    def service_count(self, obj):
        """Display number of services in this category."""
        count = obj.services.filter(is_active=True).count()
        return count
    service_count.short_description = "Active Services"


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "is_active", "created_at")
    list_filter = ("category", "is_active", "created_at")
    search_fields = ("name", "description", "category__name")
    ordering = ("category", "name")
    readonly_fields = ("created_at", "updated_at")
    
    fieldsets = (
        ("Service Information", {
            'fields': ('name', 'category', 'price')
        }),
        ("Details", {
            'fields': ('description', 'image')
        }),
        ("Status", {
            'fields': ('is_active',)
        }),
        ("Timestamps", {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
