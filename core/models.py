from django.db import models
import uuid


class Settings(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField('Chave', max_length=100, unique=True)
    value = models.TextField('Valor', blank=True, null=True)
    description = models.TextField('Descrição', blank=True)
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)
    
    class Meta:
        verbose_name = 'Configuração'
        verbose_name_plural = 'Configurações'
    
    def __str__(self):
        return self.key
    
    @classmethod
    def get(cls, key, default=None):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set(cls, key, value, description=''):
        obj, _ = cls.objects.update_or_create(key=key, defaults={'value': value, 'description': description})
        return obj


class WhatsAppMessage(models.Model):
    MESSAGE_TYPES = [
        ('reminder', 'Lembrete'),
        ('collection', 'Cobrança'),
        ('weekly', 'Cobrança semanal'),
        ('welcome', 'Boas-vindas'),
        ('thanks', 'Agradecimento'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey('clients.Client', on_delete=models.CASCADE, related_name='whatsapp_messages')
    message_type = models.CharField('Tipo', max_length=20, choices=MESSAGE_TYPES)
    message = models.TextField('Mensagem')
    sent = models.BooleanField('Enviado', default=False)
    sent_at = models.DateTimeField('Enviado em', blank=True, null=True)
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Mensagem WhatsApp'
        verbose_name_plural = 'Mensagens WhatsApp'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.client.name} - {self.get_message_type_display()}"


class WhatsAppTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField('Nome', max_length=100)
    message_type = models.CharField('Tipo', max_length=20, choices=WhatsAppMessage.MESSAGE_TYPES)
    template = models.TextField('Template')
    active = models.BooleanField('Ativo', default=True)
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Template WhatsApp'
        verbose_name_plural = 'Templates WhatsApp'
    
    def __str__(self):
        return self.name