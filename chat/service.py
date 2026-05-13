import re
from decimal import Decimal


class ChatService:
    """Serviço de chat com IA"""
    
    def __init__(self, ai_settings):
        self.ai_settings = ai_settings
        self.model = ai_settings.model
        self.api_key = ai_settings.api_key
        self.api_url = ai_settings.api_url
        self.system_prompt = ai_settings.system_prompt or self._default_system_prompt()
    
    def _default_system_prompt(self):
        return """Você é um assistente administrativo da loja Roza Vendas.

FUNCIONALIDADES DISPONÍVEIS:
1. 📦 PRODUTOS: listar, buscar, cadastrar novos produtos
2. 👥 CLIENTES: listar, buscar, cadastrar, verificar pendências
3. 🛒 VENDAS: criar, listar histórico, verificar vendas do dia/mês
4. 💰 RELATÓRIOS: vendas do dia, vendas do mês, total a receber, lucro
5. ❓ AJUDA: mostrar todas as opções disponíveis

COMANDOS ESPECÍFICOS:
- "lista produtos" ou "quais produtos tem" → lista produtos disponíveis
- "vendi para [cliente] [produto] [quantidade]" → criar venda
- "cadastra cliente [nome] [whatsapp]" → criar cliente
- "cadastra produto [nome] [preço]" → criar produto
- "quanto [cliente] deve" ou "pendências de [cliente]" → verificar dívida
- "historico de [cliente]" → ver compras do cliente
- "vendas hoje" → vendas do dia
- "vendas do mês" → vendas do mês
- "relatório" → resumo geral
- "ajuda" → mostrar todos os comandos

Quando precisar de informações adicionais (nome do cliente, produto, quantidade, preço), pergunte ao usuário de forma clara.
Sempre confirme os dados antes de executar ações importantes."""
    
    def chat(self, message, conversation_history=None):
        """Envia mensagem para a IA e retorna a resposta"""
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
        if conversation_history:
            for msg in conversation_history[-10:]:
                role = 'user' if msg.role == 'user' else 'assistant'
                messages.append({"role": role, "content": msg.content})
        
        messages.append({"role": "user", "content": message})
        
        try:
            import requests
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 800
            }
            
            response = requests.post(self.api_url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                return f"Erro na API: {response.status_code}"
                
        except Exception as e:
            return f"Erro ao conectar com a IA: {str(e)}"
    
    def extract_intent(self, message):
        """Detecta a intenção do usuário"""
        msg_lower = message.lower()
        
        intents = {
            'create_sale': [
                r'vendi\b', r'venda\b', r'vender\b', r'comprou\b', r'compra\b',
                r'vou vender\b', r'queria vender\b', r'vendeu\b', r'teve\b',
                r'fiz uma venda\b', r'fazer uma venda\b', r'nova venda\b'
            ],
            'register_client': [
                r'cadastrar\b', r'cadastro\b', r'novo cliente\b', r'cliente novo\b',
                r'registrar\b', r'nova cliente\b', r'criar cliente\b', r'adicionar cliente\b'
            ],
            'register_product': [
                r'cadastrar produto\b', r'novo produto\b', r'adicionar produto\b',
                r'criar produto\b', r'produto novo\b'
            ],
            'list_products': [
                r'produtos?\b', r'vender\b', r'tem\b', r'quais\b', r'o que tem\b',
                r'catálogo\b', r'peças\b', r'listas?\b', r'lista produtos\b'
            ],
            'check_debt': [
                r'pendente\b', r'devendo\b', r'fiado\b', r'quanto deve\b',
                r'saldo\b', r'parcelas?\b', r'quanto que\b', r'pagar\b'
            ],
            'client_history': [
                r'historico\b', r'histórico\b', r'compras de\b', r'compras do\b',
                r'vendas de\b', r'vendas do\b', r'ultimas compras\b'
            ],
            'sales_today': [
                r'vendas hoje\b', r'vendas de hoje\b', r'hj\b', r'houve hoje\b'
            ],
            'sales_month': [
                r'vendas do mês\b', r'vendas do mes\b', r'mês\b', r'mes atual\b'
            ],
            'report': [
                r'relatório\b', r'relatario\b', r'resumo\b', r'estatísticas\b',
                r'estatisticas\b', r'resposta\b', r'balanço\b'
            ],
            'help': [
                r'ajuda\b', r'comandos\b', r'o que você faz\b', r'opções\b', r'opcoes\b'
            ],
            'list_clients': [
                r'listar clientes\b', r'todos clientes\b', r'clientes\b'
            ],
            'edit_sale': [
                r'editar venda\b', r'alterar venda\b', r'modificar venda\b'
            ],
            'cancel_sale': [
                r'cancelar venda\b', r'excluir venda\b', r'remover venda\b'
            ]
        }
        
        for intent, patterns in intents.items():
            for pattern in patterns:
                if re.search(pattern, msg_lower):
                    return intent
        
        return None
    
    def extract_sale_data(self, message):
        """Extrai informações de venda da mensagem"""
        patterns = {
            'product': r'(calcinha|sutien|cueca|lingerie|bodies|meia|conjunto|pijama|fantasia|calça|blusa|saia|vestido)',
            'quantity': r'(\d+)\s*(?:unidade|und|pcs|peças|x|un)',
            'price': r'(?:R\$?\s*)?(\d+(?:[.,]\d{2})?)',
            'payment': r'(dinheiro|pix|cartão|cartão de crédito|cartão de débitor|débito)',
        }
        
        product_match = re.search(patterns['product'], message.lower())
        quantity_match = re.search(patterns['quantity'], message.lower())
        price_match = re.search(patterns['price'], message.lower())
        payment_match = re.search(patterns['payment'], message.lower())
        
        client_match = re.search(r'para\s+(\w+)|cliente\s+(\w+)', message.lower())
        
        if product_match:
            return {
                'detected': True,
                'product': product_match.group(1).title(),
                'quantity': int(quantity_match.group(1)) if quantity_match else 1,
                'price': price_match.group(1) if price_match else None,
                'payment': payment_match.group(1) if payment_match else None,
                'client_name': client_match.group(1).title() if client_match else None
            }
        
        return {'detected': False}


def get_chat_service():
    """Retorna o serviço de chat ativo"""
    from chat.models import AISettings
    ai_settings = AISettings.get_active()
    if not ai_settings:
        return None
    return ChatService(ai_settings)