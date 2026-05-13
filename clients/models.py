from django.db import models
import uuid


class Client(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField('Nome', max_length=255)
    whatsapp = models.CharField('WhatsApp', max_length=20, unique=True)
    city = models.CharField('Cidade', max_length=255, blank=True, null=True)
    observations = models.TextField('Observações', blank=True, null=True)
    total_due = models.DecimalField('Total devido', max_digits=10, decimal_places=2, default=0)
    last_purchase = models.DateTimeField('Última compra', blank=True, null=True)
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)
    
    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def formatted_whatsapp(self):
        phone = ''.join(filter(str.isdigit, self.whatsapp))
        if len(phone) == 11:
            return f"({phone[:2]}) {phone[2:7]}-{phone[7:]}"
        return self.whatsapp
    
    @property
    def is_debtor(self):
        return self.total_due > 0
    
    @property
    def days_since_last_purchase(self):
        if self.last_purchase:
            from django.utils import timezone
            return (timezone.now() - self.last_purchase).days
        return None
    
    def sync_total_due(self):
        from sales.models import Sale
        due = sum(
            float(s.total - s.paid_amount) 
            for s in Sale.objects.filter(client=self).exclude(status__in=['paid', 'canceled'])
        )
        self.total_due = due
        self.save(update_fields=['total_due', 'updated_at'])
        return due


class Payment(models.Model):
    STATUS_CHOICES = [
        ('paid', 'Pago'),
        ('partial', 'Parcial'),
        ('pending', 'Pendente'),
        ('overdue', 'Atrasado'),
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField('Valor', max_digits=10, decimal_places=2)
    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default='pending')
    due_date = models.DateField('Data de vencimento', blank=True, null=True)
    paid_date = models.DateField('Data de pagamento', blank=True, null=True)
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Pagamento'
        verbose_name_plural = 'Pagamentos'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.client.name} - {self.amount}"