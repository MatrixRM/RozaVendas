from django.contrib import admin
from .models import FinancialSummary


@admin.register(FinancialSummary)
class FinancialSummaryAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_sales', 'total_commission', 'total_profit', 'total_received', 'total_pending']
    list_filter = ['date']
    readonly_fields = ['id', 'created_at']
    ordering = ['-date']
    date_hierarchy = 'date'
    
    def has_view_permission(self, request, obj=None):
        return True
    
    def has_add_permission(self, request):
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser