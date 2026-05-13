from django.urls import path
from . import views

urlpatterns = [
    path('chat', views.chat_home, name='chat_home'),
    path('chat/settings', views.chat_settings, name='chat_settings'),
    path('chat/message', views.chat_message, name='chat_message'),
]