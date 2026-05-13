from django.urls import path
from . import views

urlpatterns = [
    path('sales', views.sales_list, name='sales_list'),
    path('sales/new', views.new_sale, name='new_sale'),
    path('sales/<uuid:pk>', views.sale_detail, name='sale_detail'),
    path('sales/<uuid:pk>/payment', views.receive_payment, name='receive_payment'),
    path('sales/<uuid:pk>/delete', views.sale_delete, name='sale_delete'),
    path('sales/<uuid:pk>/cancel', views.cancel_sale, name='cancel_sale'),
    path('api/quick-stats', views.quick_stats, name='quick_stats'),
]