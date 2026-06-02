from urllib.parse import parse_qs, urlparse

from django.test import SimpleTestCase

from core.whatsapp_bot import sanitize_client_message, send_whatsapp_message


class WhatsAppMessageTests(SimpleTestCase):
    def test_sanitize_client_message_removes_emojis(self):
        message = sanitize_client_message('Olá 😊\n✅ Pedido confirmado\n⚠️ Pendente')

        self.assertEqual(message, 'Olá\nPedido confirmado\nPendente')

    def test_send_whatsapp_message_uses_sanitized_text(self):
        result = send_whatsapp_message('11999999999', 'Recibo 🧾\nObrigado 😊')
        text = parse_qs(urlparse(result['link']).query)['text'][0]

        self.assertEqual(text, 'Recibo\nObrigado')
