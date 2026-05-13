from django.contrib import admin
from .models import Client, Payment


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'whatsapp', 'city', 'total_due', 'last_purchase', 'created_at']
    search_fields = ['name', 'whatsapp', 'city']
    list_filter = ['city', 'created_at']
    readonly_fields = ['total_due', 'last_purchase', 'id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'whatsapp', 'city')
        }),
        ('Informações Adicionais', {
            'fields': ('observations', 'total_due', 'last_purchase')
        }),
        ('Sistema', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_view_permission(self, request, obj=None):
        return True
    
    def has_add_permission(self, request):
        return request.user.has_perm('clients.add_client')
    
    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('clients.change_client')
    
    def has_delete_permission(self, request, obj=None):
        return request.user.has_perm('clients.delete_client')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['client', 'amount', 'status', 'due_date', 'paid_date', 'created_at']
    list_filter = ['status', 'due_date', 'paid_date']
    search_fields = ['client__name']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    
    def has_view_permission(self, request, obj=None):
        return True
    
    def has_add_permission(self, request):
        return request.user.has_perm('clients.add_payment')
    
    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('clients.change_payment')
    
    def has_delete_permission(self, request, obj=None):
        return request.user.has_perm('clients.delete_payment')


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ['amount', 'status', 'due_date', 'paid_date', 'created_at']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False