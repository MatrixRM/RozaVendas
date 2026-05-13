from django.urls import path
from . import views

urlpatterns = [
    path('settings', views.settings_view, name='settings'),
    path('settings/promotion', views.send_custom_promotion, name='send_promotion'),
    path('settings/random', views.random_promotion, name='random_promotion'),
    path('settings/preview', views.promo_preview, name='promo_preview'),
    path('whatsapp', views.whatsapp_panel, name='whatsapp_panel'),
    path('whatsapp/send/<uuid:client_id>', views.send_whatsapp, name='send_whatsapp'),
    path('whatsapp/bulk', views.bulk_whatsapp, name='bulk_whatsapp'),
    path('api/check-debtors', views.api_check_debtors, name='api_check_debtors'),
]