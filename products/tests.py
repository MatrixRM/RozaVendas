from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from products.models import Product


@override_settings(SECURE_SSL_REDIRECT=False)
class ProductFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='seller', password='pass12345')
        self.client.force_login(self.user)

    def test_manual_product_saves_supplier_code(self):
        response = self.client.post(reverse('product_new'), {
            'supplier_code': '1363',
            'name': 'Tanga de Micro',
            'category': 'lingerie',
            'size': 'M',
            'color': 'Preto',
            'cost': '31.80',
            'price': '39.90',
            'stock': '3',
        })

        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(supplier_code='1363')
        self.assertEqual(product.name, 'Tanga de Micro')
        self.assertEqual(product.cost, Decimal('31.80'))
        self.assertEqual(product.price, Decimal('39.90'))
        self.assertEqual(product.stock, 3)

    def test_csv_import_renders_preview_with_codes(self):
        csv_data = (
            'codigo;descricao;preco;quantidade\n'
            '1363;TANGA DE MICRO COM COS ALTO;31,80;3\n'
            '1368;TANGA DE MICRO COM DETALHE DE RENDA;28,80;3\n'
        ).encode('utf-8')
        upload = SimpleUploadedFile('produtos.csv', csv_data, content_type='text/csv')

        response = self.client.post(reverse('product_import'), {'import_file': upload})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1363')
        self.assertContains(response, 'TANGA DE MICRO COM COS ALTO')
        self.assertContains(response, 'productsData')

    def test_csv_import_accepts_file_without_header(self):
        csv_data = '1400;FIO DUPLO DE MICRO COM DETALHE;31,80;3\n'.encode('utf-8')
        upload = SimpleUploadedFile('sem_cabecalho.csv', csv_data, content_type='text/csv')

        response = self.client.post(reverse('product_import'), {'import_file': upload})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1400')
        self.assertContains(response, 'FIO DUPLO DE MICRO COM DETALHE')
