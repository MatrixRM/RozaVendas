from django.urls import path
from . import views

urlpatterns = [
    path('clients', views.clients_list, name='clients_list'),
    path('clients/new', views.client_new, name='client_new'),
    path('clients/edit/<uuid:pk>', views.client_edit, name='client_edit'),
    path('clients/detail/<uuid:pk>', views.client_detail, name='client_detail'),
    path('clients/delete/<uuid:pk>', views.client_delete, name='client_delete'),
    path('api/clients', views.api_clients, name='api_clients'),
    path('clients/sync-debts', views.sync_debts, name='sync_debts'),
]