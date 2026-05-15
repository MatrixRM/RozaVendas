from django.urls import path
from . import views

urlpatterns = [
    path('products', views.products_list, name='products_list'),
    path('products/new', views.product_new, name='product_new'),
    path('products/edit/<uuid:pk>', views.product_edit, name='product_edit'),
    path('products/delete/<uuid:pk>', views.product_delete, name='product_delete'),
    path('api/products', views.api_products, name='api_products'),
    path('products/import', views.product_import, name='product_import'),
    path('products/import/confirm', views.product_import_confirm, name='product_import_confirm'),
]