from django.contrib import admin
from .models import Settings, WhatsAppMessage, WhatsAppTemplate


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ['key', 'masked_value', 'description']
    search_fields = ['key', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    def masked_value(self, obj):
        if obj.key == 'pix_key' and obj.value:
            return '*' * (len(obj.value) - 4) + obj.value[-4:]
        return obj.value
    masked_value.short_description = 'Valor'
    
    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_add_permission(self, request):
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ['client', 'message_type', 'sent', 'sent_at', 'created_at']
    list_filter = ['message_type', 'sent', 'created_at']
    search_fields = ['client__name', 'message']
    readonly_fields = ['id', 'created_at', 'sent_at']
    ordering = ['-created_at']
    
    def has_view_permission(self, request, obj=None):
        return True
    
    def has_add_permission(self, request):
        return request.user.is_superuser or request.user.has_perm('core.add_whatsappmessage')
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(WhatsAppTemplate)
class WhatsAppTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'message_type', 'active', 'created_at']
    list_filter = ['active', 'message_type']
    search_fields = ['name', 'template']
    readonly_fields = ['id', 'created_at']
    ordering = ['-created_at']
    
    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_add_permission(self, request):
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser