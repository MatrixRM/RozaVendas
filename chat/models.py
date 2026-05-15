from django.db import models
from clients.models import Client
import uuid


class AISettings(models.Model):
    """Configurações de IA para o chat"""
    MODEL_CHOICES = [
        # OpenAI
        ('gpt-4o-mini', 'GPT-4o Mini'),
        ('gpt-4o', 'GPT-4o'),
        ('gpt-4-turbo', 'GPT-4 Turbo'),
        ('gpt-4', 'GPT-4'),
        # Anthropic
        ('claude-3-haiku', 'Claude 3 Haiku'),
        ('claude-3-sonnet', 'Claude 3 Sonnet'),
        ('claude-3-opus', 'Claude 3 Opus'),
        # Groq (sem visão)
        ('llama-3.3-70b-versatile', 'Llama 3.3 70B'),
        ('mixtral-8x7b-32768', 'Mixtral 8x7B'),
        # Google Gemini (gratuito com visão)
        ('gemini-1.5-flash-8k', 'Gemini 1.5 Flash 8K'),
    ]
    
    PROVIDER_CHOICES = [
        ('openai', 'OpenAI'),
    ]
    
    name = models.CharField('Nome', max_length=100, default='Chat IA')
    model = models.CharField('Modelo', max_length=50, choices=MODEL_CHOICES, default='gpt-4o-mini')
    provider = models.CharField('Provedor', max_length=20, choices=PROVIDER_CHOICES, default='openai')
    api_key = models.CharField('API Key', max_length=500, blank=True)
    api_url = models.URLField('URL da API', default='https://api.openai.com/v1/chat/completions')
    system_prompt = models.TextField('Prompt do Sistema', default='')
    active = models.BooleanField('Ativo', default=False)
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)
    
    class Meta:
        verbose_name = 'Configuração de IA'
        verbose_name_plural = 'Configurações de IA'
    
    def __str__(self):
        return f"{self.name} - {self.model} ({'Ativo' if self.active else 'Inativo'})"
    
    @classmethod
    def get_active(cls):
        return cls.objects.filter(active=True).first()


class ChatConversation(models.Model):
    """Conversa do chat"""
    STATUS_CHOICES = [
        ('active', 'Ativa'),
        ('closed', 'Encerrada'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='chats')
    phone = models.CharField('Telefone', max_length=20, blank=True)
    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)
    
    class Meta:
        verbose_name = 'Conversa'
        verbose_name_plural = 'Conversas'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Chat {self.id} - {self.client.name if self.client else self.phone}"
    
    def get_last_message(self):
        return self.messages.last()


class ChatMessage(models.Model):
    """Mensagem do chat"""
    ROLE_CHOICES = [
        ('user', 'Cliente'),
        ('assistant', 'Assistente'),
        ('system', 'Sistema'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(ChatConversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField('Papel', max_length=20, choices=ROLE_CHOICES)
    content = models.TextField('Conteúdo')
    audio_url = models.CharField('URL do Áudio', max_length=500, blank=True)
    metadata = models.JSONField('Metadados', default=dict, blank=True)
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Mensagem'
        verbose_name_plural = 'Mensagens'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.get_role_display()}: {self.content[:50]}..."