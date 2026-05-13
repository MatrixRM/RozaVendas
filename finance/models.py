from django.db import models
import uuid


class FinancialSummary(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField('Data', unique=True)
    total_sales = models.DecimalField('Total vendas', max_digits=10, decimal_places=2, default=0)
    total_commission = models.DecimalField('Total comissão', max_digits=10, decimal_places=2, default=0)
    total_profit = models.DecimalField('Total lucro', max_digits=10, decimal_places=2, default=0)
    total_received = models.DecimalField('Total recebido', max_digits=10, decimal_places=2, default=0)
    total_pending = models.DecimalField('Total pendente', max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Resumo financeiro'
        verbose_name_plural = 'Resumos financeiros'
        ordering = ['-date']
    
    def __str__(self):
        return f"Resumo {self.date}"