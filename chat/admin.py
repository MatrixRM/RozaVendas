from django.contrib import admin
from .models import AISettings, ChatConversation, ChatMessage


@admin.register(AISettings)
class AISettingsAdmin(admin.ModelAdmin):
    list_display = ['name', 'model', 'active', 'created_at']
    list_filter = ['active', 'model']
    search_fields = ['name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'api_key']
    ordering = ['-created_at']
    
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['id', 'created_at', 'updated_at', 'api_key']
        return ['id', 'created_at', 'updated_at']
    
    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_add_permission(self, request):
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'phone', 'status', 'created_at', 'updated_at']
    list_filter = ['status', 'created_at']
    search_fields = ['client__name', 'phone']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-updated_at']
    
    def has_view_permission(self, request, obj=None):
        return True
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'conversation', 'role', 'content_preview', 'created_at']
    list_filter = ['role', 'created_at']
    search_fields = ['content']
    readonly_fields = ['id', 'created_at']
    ordering = ['created_at']
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Conteúdo'
    
    def has_view_permission(self, request, obj=None):
        return True
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser