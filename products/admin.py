from django.contrib import admin
from .models import Product, Category


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'size', 'color', 'price', 'cost', 'stock', 'active', 'created_at']
    list_filter = ['category', 'active', 'size', 'color']
    search_fields = ['name', 'color']
    list_editable = ['active', 'stock']
    readonly_fields = ['id', 'created_at', 'updated_at', 'profit']
    ordering = ['name']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'category', 'size', 'color')
        }),
        ('Valores', {
            'fields': ('cost', 'price', 'stock', 'active')
        }),
        ('Imagem', {
            'fields': ('image',)
        }),
        ('Sistema', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_view_permission(self, request, obj=None):
        return True
    
    def has_add_permission(self, request):
        return request.user.has_perm('products.add_product')
    
    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('products.change_product')
    
    def has_delete_permission(self, request, obj=None):
        return request.user.has_perm('products.delete_product')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']
    
    def has_view_permission(self, request, obj=None):
        return True
    
    def has_add_permission(self, request):
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser