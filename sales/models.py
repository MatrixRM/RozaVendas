from django.db import models
from django.conf import settings
from clients.models import Client
from products.models import Product
import uuid
import json


class Sale(models.Model):
    PAYMENT_TYPES = [
        ('cash', 'Dinheiro'),
        ('pix', 'PIX'),
        ('card', 'Cartão'),
        ('debit', 'Débito'),
    ]
    
    STATUS_CHOICES = [
        ('paid', 'Pago'),
        ('partial', 'Parcial'),
        ('pending', 'Pendente'),
        ('overdue', 'Atrasado'),
        ('canceled', 'Cancelado'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    products = models.JSONField('Produtos', default=list)
    total = models.DecimalField('Total', max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField('Valor pago', max_digits=10, decimal_places=2, default=0)
    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default='pending')
    commission = models.DecimalField('Comissão (35%)', max_digits=10, decimal_places=2, default=0)
    profit = models.DecimalField('Lucro', max_digits=10, decimal_places=2, default=0)
    payment_type = models.CharField('Forma de pagamento', max_length=20, choices=PAYMENT_TYPES, default='cash')
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Venda'
        verbose_name_plural = 'Vendas'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Venda {self.id} - {self.total}"
    
    def save(self, *args, **kwargs):
        commission_rate = self._get_commission_rate()
        if not self.commission:
            self.commission = self.total * commission_rate
        
        if self.status in ['pending', 'partial'] and self.created_at and self._is_overdue():
            self.status = 'overdue'
        
        super().save(*args, **kwargs)
    
    def _is_overdue(self):
        from django.utils import timezone
        from core.models import Settings
        days = int(Settings.get('overdue_days', 7))
        return (timezone.now().date() - self.created_at.date()).days >= days
    
    def _get_commission_rate(self):
        from core.models import Settings
        rate = Settings.get('commission_rate', None)
        if rate:
            try:
                return float(rate) / 100
            except (ValueError, TypeError):
                pass
        return settings.COMISSION_RATE
    
    @property
    def pending_amount(self):
        return self.total - self.paid_amount
    
    @property
    def is_paid(self):
        return self.status == 'paid'
    
    @property
    def days_overdue(self):
        if self.status in ['pending', 'overdue']:
            from django.utils import timezone
            return (timezone.now().date() - self.created_at.date()).days
        return 0
    
    def get_products_list(self):
        return json.loads(self.products) if isinstance(self.products, str) else self.products