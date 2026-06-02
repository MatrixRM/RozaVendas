import json
from decimal import Decimal
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from clients.models import Client
from products.models import Product
from sales.models import Sale
from sales.views import send_sale_receipt


@override_settings(SECURE_SSL_REDIRECT=False)
class SaleFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='seller', password='pass12345')
        self.client.force_login(self.user)
        self.customer = Client.objects.create(name='Cliente Teste', whatsapp='11999999999')
        self.product = Product.objects.create(
            name='Produto Teste',
            category='lingerie',
            cost=Decimal('10.00'),
            price=Decimal('20.00'),
            stock=2,
        )

    def post_sale(self, quantity=1, paid_amount='0'):
        payload = {
            'client_id': str(self.customer.id),
            'products': [{'id': str(self.product.id), 'quantity': quantity}],
            'payment_type': 'pix',
            'paid_amount': paid_amount,
        }
        with patch('sales.views.send_sale_receipt', return_value=None):
            return self.client.post(
                reverse('new_sale'),
                data=json.dumps(payload),
                content_type='application/json',
            )

    def test_sale_uses_database_price_and_decrements_stock(self):
        response = self.post_sale(quantity=2, paid_amount='20.00')

        self.assertEqual(response.status_code, 200)
        sale = Sale.objects.get()
        self.product.refresh_from_db()
        self.customer.refresh_from_db()

        self.assertEqual(sale.total, Decimal('40.00'))
        self.assertEqual(sale.paid_amount, Decimal('20.00'))
        self.assertEqual(sale.status, 'partial')
        self.assertEqual(sale.payment_type, 'pix')
        self.assertEqual(sale.profit, Decimal('20.00'))
        self.assertEqual(self.product.stock, 0)
        self.assertEqual(self.customer.total_due, Decimal('20.00'))

    def test_new_sale_page_renders_simple_client_picker(self):
        response = self.client.get(reverse('new_sale'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="selectedClientId"')
        self.assertContains(response, 'id="clientQuickSearch"')
        self.assertContains(response, 'class="client-card-option')
        self.assertContains(response, 'Cliente Teste')
        self.assertContains(response, 'card hidden')

    def test_sale_rejects_quantity_above_stock(self):
        response = self.post_sale(quantity=3)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Sale.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 2)

    def test_payment_cannot_exceed_pending_amount(self):
        self.post_sale(quantity=1, paid_amount='0')
        sale = Sale.objects.get()

        response = self.client.post(
            reverse('receive_payment', args=[sale.id]),
            data={'amount': '25.00', 'payment_type': 'cash'},
        )

        self.assertEqual(response.status_code, 302)
        sale.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(sale.paid_amount, Decimal('0.00'))
        self.assertEqual(sale.status, 'pending')
        self.assertEqual(self.customer.total_due, Decimal('20.00'))

    def test_cancel_sale_restores_stock_once(self):
        self.post_sale(quantity=1, paid_amount='0')
        sale = Sale.objects.get()

        first = self.client.post(reverse('cancel_sale', args=[sale.id]))
        second = self.client.post(reverse('cancel_sale', args=[sale.id]))

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.product.refresh_from_db()
        sale.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(self.product.stock, 2)
        self.assertEqual(sale.status, 'canceled')
        self.assertEqual(self.customer.total_due, Decimal('0.00'))

    def test_sale_receipt_message_has_no_emojis(self):
        sale = Sale.objects.create(
            client=self.customer,
            products=[{'id': str(self.product.id), 'name': self.product.name, 'price': 20.0, 'quantity': 1}],
            total=Decimal('20.00'),
            paid_amount=Decimal('20.00'),
            status='paid',
            commission=Decimal('7.00'),
            profit=Decimal('10.00'),
            payment_type='pix',
        )

        result = send_sale_receipt(self.customer, sale)
        text = parse_qs(urlparse(result['link']).query)['text'][0]

        self.assertIn('Recibo:', text)
        self.assertIn('Pagamento: pago', text)
        self.assertNotIn('😊', text)
        self.assertNotIn('🧾', text)
        self.assertNotIn('✅', text)
