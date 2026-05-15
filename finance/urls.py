from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('debtors', views.debtors_list, name='debtors_list'),
    path('reports', views.reports, name='reports'),
    path('reports/pdf', views.sales_pdf, name='sales_pdf'),
]