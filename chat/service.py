import re
import base64
from decimal import Decimal


class ChatService:
    """Serviço de chat com IA"""
    
    def __init__(self, ai_settings):
        self.ai_settings = ai_settings
        self.model = ai_settings.model
        self.api_key = ai_settings.api_key
        self.provider = getattr(ai_settings, 'provider', 'openai')
        
        # Definir URL base conforme provedor
        if self.provider == 'openai':
            self.api_url = 'https://api.openai.com/v1/chat/completions'
        else:
            self.api_url = 'https://api.openai.com/v1/chat/completions'
        
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
                r'fiz uma venda\b', r'fazer uma venda\b', r'nova venda\b',
                r'foi vendido\b', r'vendem\b', r'vendido\b', r'vendido\s+\d+',
                r'tá vendido\b', r'está vendido\b', r'levou\b', r'pegou\b'
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
            ],
            'upload_product_list': [
                r'importar produtos\b', r'cadastrar produtos\b', r'lista de produtos\b',
                r'cadastrar em lote\b', r'foto de produtos\b', r'imagem de produtos\b',
                r'tabela de preços\b', r'catálogo\b', r'cadastro em massa\b'
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


def parse_product_list_from_text(text):
    """Extrai lista de produtos do texto com validação rigorosa"""
    products = []
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 3:
            continue
        
        lower = line.lower()
        if any(skip in lower for skip in ['não', 'consegui', 'identificar', 'ajudar', 'entender', 'formato', 'não consegui', 'json', 'produtos']):
            continue
        
        # Tentar múltiplos formatos
        # Formato: código | nome | preço | quantidade
        patterns = [
            r'(\d{2,5})\s*[\|\-]\s*([A-Za-zÀ-ÖØ-öø-ÿ\s]+?)\s*[\|\-]\s*([\d.,]+)\s*[\|\-]\s*(\d+)',
            # Formato: código nome preço qtd
            r'(\d{2,5})\s+([A-Za-zÀ-ÖØ-öø-ÿ\s]+?)\s+([\d.,]+)\s+(\d+)',
            # Formato: código - nome - R$ preço - qtd
            r'(\d{2,5})\s*[-–]\s*([A-Za-zÀ-ÖØ-öø-ÿ\s]+?)\s*[-–]\s*R?\$?\s*([\d.,]+)\s*[-–]\s*(\d+)',
        ]
        
        matched = False
        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                groups = match.groups()
                code = groups[0]
                
                # Validar código é número razoável
                if not code.isdigit() or int(code) > 99999:
                    continue
                
                name = groups[1].strip()
                if len(name) < 2:
                    continue
                
                try:
                    # Validar preço
                    price_str = groups[2].replace(',', '.')
                    price = float(price_str)
                    if price <= 0 or price > 10000:  # Preço razoável
                        continue
                except:
                    continue
                
                try:
                    # Validar quantidade
                    quantity = int(groups[3])
                    if quantity < 1 or quantity > 9999:
                        quantity = 1
                except:
                    quantity = 1
                
                products.append({
                    'codigo': code,
                    'nome': name.upper(),
                    'preco': price,
                    'quantidade': quantity
                })
                matched = True
                break
        
        # Se não encontrou com padrões, tentar extrair qualquer linha com código numérico
        if not matched:
            code_match = re.search(r'^(\d{2,5})[\s\|\-]', line)
            if code_match:
                code = code_match.group(1)
                # Tentar extrair preço
                price_match = re.search(r'([\d.,]+)', line)
                if price_match:
                    try:
                        price = float(price_match.group(1).replace(',', '.'))
                        if price > 0 and price < 10000:
                            # Remover código e preço do nome
                            name = re.sub(r'^(\d+[\s\|\-]*)', '', line, count=1)
                            name = re.sub(r'[\d.,]+$', '', name).strip()
                            name = re.sub(r'[\d.,]+\s*$', '', name).strip()
                            
                            if len(name) >= 2:
                                products.append({
                                    'codigo': code,
                                    'nome': name.upper()[:50],
                                    'preco': price,
                                    'quantidade': 1
                                })
                    except:
                        pass
    
    return products