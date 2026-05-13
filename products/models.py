from django.db import models
import uuid


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    
    class Meta:
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Product(models.Model):
    CATEGORIES = [
        ('lingerie', 'Lingerie'),
        ('cueca', 'Cueca'),
        ('meia', 'Meia'),
        ('camiseta', 'Camiseta'),
        ('moletom', 'Moletom'),
        ('legging', 'Legging'),
        ('segunda_pele', 'Segunda pele'),
    ]
    
    SIZES = [
        ('PP', 'PP'),
        ('P', 'P'),
        ('M', 'M'),
        ('G', 'G'),
        ('GG', 'GG'),
        ('XG', 'XG'),
        ('UN', 'Único'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField('Nome', max_length=255)
    category = models.CharField('Categoria', max_length=50, choices=CATEGORIES)
    size = models.CharField('Tamanho', max_length=10, choices=SIZES, blank=True, null=True)
    color = models.CharField('Cor', max_length=100, blank=True, null=True)
    cost = models.DecimalField('Custo', max_digits=10, decimal_places=2, default=0)
    price = models.DecimalField('Preço de venda', max_digits=10, decimal_places=2)
    stock = models.IntegerField('Estoque', default=0)
    image = models.ImageField('Foto', upload_to='products/', blank=True, null=True)
    active = models.BooleanField('Ativo', default=True)
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)
    
    class Meta:
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.size or 'UN'}"
    
    @property
    def profit(self):
        return self.price - self.cost
    
    @property
    def profit_margin(self):
        if self.price > 0:
            return ((self.price - self.cost) / self.price) * 100
        return 0