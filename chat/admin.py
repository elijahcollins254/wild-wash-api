from django import forms
from django.contrib import admin

from .models import SupportConversation, SupportMessage


class SupportMessageInlineForm(forms.ModelForm):
    class Meta:
        model = SupportMessage
        fields = ('body',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['body'].disabled = True


class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    form = SupportMessageInlineForm
    fields = ('body', 'sender', 'is_from_support', 'created_at')
    readonly_fields = ('sender', 'is_from_support', 'created_at')
    extra = 1
    can_delete = False


@admin.register(SupportConversation)
class SupportConversationAdmin(admin.ModelAdmin):
    list_display = ('customer', 'created_at', 'updated_at')
    search_fields = ('customer__username', 'customer__email', 'customer__phone')
    readonly_fields = ('customer', 'created_at', 'updated_at')
    inlines = (SupportMessageInline,)
    ordering = ('-updated_at',)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if not instance.pk:
                instance.sender = request.user
                instance.is_from_support = True
                instance.save()
        formset.save_m2m()
