from django.urls import path
from . import views

urlpatterns = [
    path('chat', views.chat_home, name='chat_home'),
    path('chat/history', views.chat_history, name='chat_history'),
    path('chat/settings', views.chat_settings, name='chat_settings'),
    path('chat/message', views.chat_message, name='chat_message'),
    path('chat/confirm-import', views.confirm_import_products, name='confirm_import_products'),
    path('chat/cancel-import', views.cancel_import_products, name='cancel_import_products'),
    path('chat/audio', views.chat_audio, name='chat_audio'),
]