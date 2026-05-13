from django.contrib import admin
from django.db.models import Sum
from .models import Sale


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'total', 'paid_amount', 'status', 'payment_type', 'created_at']
    list_filter = ['status', 'payment_type', 'created_at']
    search_fields = ['client__name', 'id']
    readonly_fields = ['commission', 'profit', 'id', 'created_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Informações', {
            'fields': ('id', 'client', 'created_at')
        }),
        ('Produtos', {
            'fields': ('products',)
        }),
        ('Valores', {
            'fields': ('total', 'paid_amount', 'status', 'payment_type', 'commission', 'profit')
        }),
    )
    
    def has_view_permission(self, request, obj=None):
        return True
    
    def has_add_permission(self, request):
        return request.user.has_perm('sales.add_sale')
    
    def has_change_permission(self, request, obj=None):
        if obj is None:
            return request.user.has_perm('sales.change_sale')
        return request.user.has_perm('sales.change_sale')
    
    def has_delete_permission(self, request, obj=None):
        return request.user.has_perm('sales.delete_sale')
    
    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status == 'paid':
            return ['client', 'products', 'total', 'payment_type', 'commission', 'profit']
        return self.readonly_fields


class SaleInline(admin.TabularInline):
    model = Sale
    extra = 0
    readonly_fields = ['id', 'total', 'status', 'created_at']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False