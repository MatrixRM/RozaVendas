# -*- coding: utf-8 -*-
import re
import base64
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Sum, Count
from django.conf import settings
from clients.models import Client
from products.models import Product
from sales.models import Sale
from .models import AISettings, ChatConversation, ChatMessage
from .service import get_chat_service, parse_product_list_from_text


@login_required
def chat_history(request):
    """Retorna o histórico de mensagens em JSON"""
    try:
        # Pegar todas as conversas com mensagens (exceto a ativa)
        conversations = ChatConversation.objects.filter(
            status='closed'
        ).order_by('-updated_at')[:10]
        
        if not conversations:
            # Se não houver conversas fechadas, pegar as mais antigas
            conversations = ChatConversation.objects.order_by('-updated_at')[:5]
        
        all_messages = []
        for conv in conversations:
            try:
                client_name = conv.client.name if conv.client else (conv.phone or 'Sem nome')
            except:
                client_name = 'Sem nome'
            
            conv_messages = conv.messages.all()
            for msg in conv_messages:
                # Filtrar mensagens de boas-vindas
                content = msg.content
                if 'Bem-vinda' not in content and 'Olá! Sou o assistente' not in content:
                    all_messages.append({
                        'role': msg.role,
                        'content': content,
                        'created_at': msg.created_at.isoformat(),
                        'conversation': client_name
                    })
        
        # Ordenar por data
        all_messages.sort(key=lambda x: x['created_at'], reverse=True)
        
        return JsonResponse({'messages': all_messages[:50]})
    except Exception as e:
        return JsonResponse({'messages': [], 'error': str(e)}, status=200)


@login_required
@require_http_methods(["POST"])
def chat_audio(request):
    """Transcreve áudio usando Whisper"""
    audio_base64 = request.POST.get('audio', '')
    
    if not audio_base64:
        return JsonResponse({'error': 'Áudio não fornecido'}, status=400)
    
    # Remover prefixo se houver
    if ',' in audio_base64:
        audio_base64 = audio_base64.split(',')[1]
    
    try:
        import requests
        import base64
        
        # Obter API key do ChatService
        chat_service = get_chat_service()
        if not chat_service:
            return JsonResponse({'error': 'Chat IA não configurado'}, status=400)
        
        # Decodificar áudio
        audio_bytes = base64.b64decode(audio_base64)
        
        # Usar API OpenAI Whisper
        # O endpoint correto para Whisper é: https://api.openai.com/v1/audio/transcriptions
        
        # Primeiro, fazer upload do arquivo de áudio
        files = {
            'file': ('audio.webm', audio_bytes, 'audio/webm'),
            'model': (None, 'whisper-1'),
        }
        
        data = {
            'model': 'whisper-1',
            'language': 'pt',  # Português
            'response_format': 'text',
        }
        
        headers = {
            'Authorization': f'Bearer {chat_service.api_key}',
        }
        
        response = requests.post(
            'https://api.openai.com/v1/audio/transcriptions',
            headers=headers,
            files=files,
            data=data,
            timeout=30
        )
        
        if response.status_code == 200:
            text = response.text.strip()
            return JsonResponse({'text': text})
        else:
            return JsonResponse({'error': f'Erro {response.status_code}: {response.text[:100]}'}, status=400)
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def compress_image(image_data, max_size=1200, quality=80):
    """Comprime imagem para reducir custo e melhorar precisao"""
    try:
        from io import BytesIO
        from PIL import Image
        
        img_bytes = base64.b64decode(image_data)
        img = Image.open(BytesIO(img_bytes))
        
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=quality)
        return base64.b64encode(buffer.getvalue()).decode()
    except:
        return image_data


def auto_categorize(name):
    """Categoriza automaticamente baseado no nome do produto"""
    name_upper = name.upper()
    
    categories = {
        'roupas': ['CALCA', 'JEANS', 'MOLETOM', 'BERMUDA', 'SHORT', 'SAIA', 'VESTIDO', 'BLUSA', 'CAMISETA', 'JARDINEIRA', 'SHORTS', 'BERMUDA', 'VISCOSE', 'MOLETOM', 'FIT', 'JOGGER', 'MACACAO'],
        'cuecas': ['CUECA', 'CALCAO', 'SLIP', 'CALCAO BOXER'],
        'sutia': ['SUTIA', 'BRA', 'BUSTIE', 'TOP', 'SOUTIEN', 'TOP ', 'BUSTIEN'],
        'calcinha': ['CALCINHA', 'FIO DENTAL', 'CARDIGUE', 'TANGA', 'TANGUE', 'TANG'],
        'pijamas': ['PIJAMA', 'CAMISOLA', 'JOGGER', 'PIJAMAS'],
        'meias': ['MEIA', 'MEIAS'],
        'lingerie': ['CONJUNTO', 'BODY', 'MODAL', 'CROP', 'LINGERIE', 'CUE'],
        'infantil': ['INFANTIL', 'CRIANCA', 'MENINA', 'MENINO', 'BEBE', 'KID', 'MENINA', 'MENINO'],
    }
    
    for category, keywords in categories.items():
        for kw in keywords:
            if kw in name_upper:
                return category
    
    return 'outros'


def validate_category_consistency(name, category):
    """Verifica se a categoria bate com o nome, corrige se necessário"""
    name_upper = name.upper()
    
    # Palavras-chave por categoria
    category_keywords = {
        'roupas': ['CALCA', 'JEANS', 'MOLETOM', 'BERMUDA', 'SHORT', 'SAIA', 'VESTIDO', 'BLUSA', 'JARDINEIRA', 'SHORTS', 'VISCOSE', 'FIT', 'JOGGER', 'MACACAO'],
        'cuecas': ['CUECA', 'CALCAO', 'SLIP', 'BOXER'],
        'sutia': ['SUTIA', 'BRA', 'BUSTIE', 'TOP', 'SOUTIEN'],
        'calcinha': ['CALCINHA', 'TANGA', 'TANGUE', 'FIO DENTAL', 'CARDIGUE', 'TANG'],
        'pijamas': ['PIJAMA', 'CAMISOLA', 'JOGGER', 'PIJAMAS'],
        'meias': ['MEIA', 'MEIAS'],
        'lingerie': ['CONJUNTO', 'BODY', 'MODAL', 'CROP', 'LINGERIE'],
        'infantil': ['INFANTIL', 'CRIANCA', 'MENINA', 'MENINO', 'BEBE', 'KID'],
    }
    
    # Verificar qual categoria combina com o nome
    for cat, keywords in category_keywords.items():
        for kw in keywords:
            if kw in name_upper:
                # Se a categoria atual é diferente da esperada, corrigir
                if category != cat and cat != 'lingerie':  # Lingerie é genérico demais
                    return cat
                elif category == 'lingerie' and cat != 'lingerie':
                    return cat
    
    # Se o nome contém certas palavras mas categoria é "outros", corrigir
    if category == 'outros' or not category:
        return auto_categorize(name)
    
    return category


@login_required
@require_http_methods(["POST"])
def confirm_import_products(request):
    """Confirma e salva os produtos pendentes da sessão"""
    products = request.session.get('pending_products', [])
    
    if not products:
        return JsonResponse({'error': 'Nenhum produto pendente'}, status=400)
    
    created = 0
    updated = 0
    errors = []
    
    for p in products:
        try:
            existing = Product.objects.filter(supplier_code=p['codigo']).first()
            if existing:
                existing.stock += p['quantidade']
                existing.price = p['preco']
                existing.name = p['nome']
                existing.category = p['categoria']
                existing.save()
                updated += 1
            else:
                from core.models import Settings
                from django.conf import settings
                cost = p['preco']
                profit_margin = float(Settings.get('profit_margin', '5'))
                selling_price = cost * (1 + profit_margin / 100)
                
                Product.objects.create(
                    name=p['nome'],
                    category=p['categoria'],
                    price=selling_price,
                    cost=cost,
                    stock=p['quantidade'],
                    supplier_code=p['codigo'],
                    active=True
                )
                created += 1
        except Exception as e:
            errors.append(f"{p.get('nome', 'Produto')}: {str(e)}")
    
    del request.session['pending_products']
    
    msg = f"✅ Importação concluída!\n\n✨ {created} produtos criados\n🔄 {updated} produtos atualizados"
    if errors:
        msg += f"\n⚠️ {len(errors)} erros"
    
    return JsonResponse({'message': msg, 'created': created, 'updated': updated, 'errors': len(errors)})


@login_required
@require_http_methods(["POST"])
def cancel_import_products(request):
    """Cancela a importação pendente"""
    if 'pending_products' in request.session:
        del request.session['pending_products']
    return JsonResponse({'message': 'Importação cancelada.'})


@login_required
def chat_home(request):
    conversation = ChatConversation.objects.filter(status='active').first()
    if not conversation:
        conversation = ChatConversation.objects.create(status='active')
    
    # Não carregar histórico no chat - cada sessão começa limpa
    messages = []
    
    return render(request, 'chat/home.html', {
        'conversation': conversation,
        'messages': messages
    })


@login_required
@require_http_methods(["POST"])
def chat_message(request):
    message = request.POST.get('message', '').strip()
    image_data = request.POST.get('image', '')
    
    if not message and not image_data:
        return JsonResponse({'error': 'Mensagem ou imagem vazia'}, status=400)
    
    conversation = ChatConversation.objects.filter(status='active').first()
    if not conversation:
        conversation = ChatConversation.objects.create(status='active')
    
    if message:
        ChatMessage.objects.create(
            conversation=conversation,
            role='user',
            content=message
        )
    
    chat_service = get_chat_service()
    
    if image_data:
        return process_product_image(request, image_data, chat_service)
    
    if chat_service:
        intent = chat_service.extract_intent(message)
        
        if intent == 'upload_product_list':
            response_data = {
                'message': "Por favor, envie a foto da lista de produtos que deseja cadastrar.",
                'action': 'upload_product_image'
            }
        else:
            response_data = process_intent(intent, message, chat_service)
        
        if isinstance(response_data, dict) and 'message' in response_data:
            ChatMessage.objects.create(
                conversation=conversation,
                role='assistant',
                content=response_data['message']
            )
        
        return JsonResponse(response_data)
    else:
        response_data = {
            'message': "Configure o Chat IA em Configurações para usar recursos avançados.",
            'action': None
        }
        ChatMessage.objects.create(
            conversation=conversation,
            role='assistant',
            content=response_data['message']
        )
        return JsonResponse(response_data)


def process_product_image(request, image_data, chat_service):
    """Processa imagem de lista de produtos usando GPT-4 Vision (funciona no PythonAnywhere)"""
    if not chat_service:
        return JsonResponse({
            'message': "Configure o Chat IA para processar imagens.",
            'action': None
        })
    
    try:
        # Comprimir imagem antes de enviar (reduz custo ~70%)
        image_data = compress_image(image_data)
        
        # Prompt ultra-simples
        prompt = """Liste todos os produtos visiveis nesta lista.

Formato (CSV simples):
codigo,nome,preco,quantidade

Exemplo:
107,TANGA,26.90,6
108,CALCINHA,31.90,4

Regras:
- Liste TODOS os produtos
- Nao invente nada
- Use ponto para decimal"""

        messages = [
            {"role": "system", "content": "Voce extrai dados de listas de produtos em CSV simples."},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
                {"type": "text", "text": prompt}
            ]}
        ]
        
        import requests
        headers = {
            "Authorization": f"Bearer {chat_service.api_key}",
            "Content-Type": "application/json"
        }
        
        # GPT-4o-mini não suporta visão, forçar gpt-4o
        model_to_use = 'gpt-4o'
        
        data = {
            "model": model_to_use,
            "messages": messages,
            "max_tokens": 4000
        }
        
        response = requests.post(chat_service.api_url, headers=headers, json=data, timeout=90)
        
        if response.status_code == 200:
            result = response.json()
            extracted_text = result['choices'][0]['message']['content']
            
            products = []
            total_linhas_vistas = 0
            linhas_perdidas = 0
            
            # Tentar parsear CSV primeiro
            lines = extracted_text.strip().split('\n')
            csv_products = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Pular linhas que não são dados (Headers, mensagens, etc)
                if line.lower().startswith('codigo') or line.lower().startswith('produto') or 'total' in line.lower():
                    continue
                
                # Parse CSV: codigo,nome,preco,quantidade
                parts = line.split(',')
                if len(parts) >= 2:
                    try:
                        code = parts[0].strip()
                        name = parts[1].strip()
                        price = float(parts[2].strip().replace(',', '.')) if len(parts) > 2 and parts[2].strip() else 0
                        quantity = int(parts[3].strip()) if len(parts) > 3 and parts[3].strip() else 1
                        
                        if code and name:
                            csv_products.append({
                                'codigo': code,
                                'nome': name,
                                'preco': price,
                                'quantidade': quantity
                            })
                    except:
                        continue
            
            if csv_products:
                products = csv_products
                total_linhas_vistas = len(products)
            else:
                # Fallback para parser de texto
                products = parse_product_list_from_text(extracted_text)
                total_linhas_vistas = len(products)
            
            # Validar cada produto - aceitar mais para não perder produtos
            validated_products = []
            for p in products:
                # Validar código - aceitar qualquer código numérico
                code = str(p.get('codigo', p.get('code', ''))).strip()
                if not code:
                    continue
                
                # Validar preço - aceitar > 0 e < 10000
                try:
                    price = float(str(p.get('preco', p.get('price', 0))).replace(',', '.'))
                    if price <= 0 or price > 10000:
                        continue
                except:
                    continue
                
                # Validar quantidade - aceitar 1-999
                try:
                    quantity = int(p.get('quantidade', p.get('qtd', p.get('quantity', 1))))
                    if quantity < 1 or quantity > 999:
                        quantity = 1
                except:
                    quantity = 1
                
                # Validar nome - aceitar qualquer nome com pelo menos 1 caractere
                name = p.get('nome', p.get('name', 'Produto')).strip()
                if len(name) < 1:
                    name = 'PRODUTO'
                
                # Verificar se a IA marcou como suspeito
                suspicious = p.get('suspeito', False) or p.get('suspeito', False) or p.get('duvidoso', False)
                
                # Confidence da IA (default 0.8 se não especificado)
                confidence = float(p.get('confidence', 0.8))
                
                # Detectar código suspeito por padrão
                if re.match(r'^[127]{3,}$', code):  # Ex: 111, 222, 777
                    suspicious = True
                
                # Categorizar - sempre verificar se bate com o nome
                category = p.get('categoria', 'outros')
                if not category or category == 'outros':
                    category = auto_categorize(name)
                else:
                    # Verificar consistência entre nome e categoria
                    category = validate_category_consistency(name, category)
                
                validated_products.append({
                    'codigo': code,
                    'nome': name.upper(),
                    'preco': price,
                    'quantidade': quantity,
                    'categoria': category,
                    'suspeito': suspicious,
                    'confidence': confidence
                })
            
            if validated_products:
                # Mostrar preview em vez de criar direto
                preview_msg = f"📋 Encontrei {len(validated_products)} produtos"
                
                # Contar produtos suspeitos
                suspicious_count = sum(1 for p in validated_products if p.get('suspeito'))
                
                # Calcular percentuais
                lost_percentage = 0
                if total_linhas_vistas > 0:
                    lost_percentage = (linhas_perdidas / total_linhas_vistas) * 100
                elif linhas_perdidas > 0:
                    lost_percentage = 50  # default se diketahui
                
                # Modo seguro: se muitos problemas, bloquear auto-save
                suspicious_percentage = (suspicious_count / len(validated_products) * 100) if validated_products else 0
                
                is_safe = True
                if lost_percentage > 20:
                    is_safe = False
                if suspicious_percentage > 30:
                    is_safe = False
                
                # Mostrar alertas
                if not is_safe:
                    preview_msg += "\n\n⚠️ MODO SEGURO ATIVADO - Revisao obrigatoria"
                
                if linhas_perdidas > 0:
                    preview_msg += f" ⚠️ ({linhas_perdidas} linhas nao interpretadas)"
                elif total_linhas_vistas > len(validated_products):
                    preview_msg += f" ⚠️ ({total_linhas_vistas - len(validated_products)} linhas incompletas)"
                
                if suspicious_count > 0:
                    preview_msg += f"\n⚠️ {suspicious_count} produtos com possiveis erros"
                
                preview_msg += "\n\nConfirme antes de cadastrar:\n"
                
                # Destacar produtos suspeitos
                for p in validated_products[:15]:
                    prefix = "⚠️" if p.get('suspeito') else "•"
                    preview_msg += f"{prefix} {p['codigo']} - {p['nome'][:25]} - R$ {p['preco']:.2f} x{p['quantidade']}\n"
                if len(validated_products) > 15:
                    preview_msg += f"\n... e mais {len(validated_products) - 15} produtos"
                
                # Salvar na sessão para confirmação
                request.session['pending_products'] = validated_products
                
                # Definir acao based on segurança
                action = 'review_required' if not is_safe else 'preview_products'
                
                return JsonResponse({
                    'message': preview_msg,
                    'action': action,
                    'products': validated_products[:15],
                    'total_count': len(validated_products),
                    'linhas_perdidas': linhas_perdidas,
                    'total_linhas_vistas': total_linhas_vistas,
                    'suspicious_count': suspicious_count,
                    'is_safe': is_safe
                })
            else:
                return JsonResponse({
                    'message': "Não consegui identificar produtos válidos na imagem. Por favor, tente uma foto mais clara ou use o cadastro manual.",
                    'action': 'ask_product_format'
                })
        else:
            return JsonResponse({
                'message': f"Erro ao processar imagem: {response.status_code}",
                'action': None
            })
            
    except Exception as e:
        return JsonResponse({
            'message': f"Erro ao processar imagem: {str(e)}",
            'action': None
        })


def process_intent(intent, message, chat_service):
    """Processa a intent do usuario e retorna a resposta"""
    msg_lower = message.lower()
    
    if intent == 'create_sale':
        return handle_create_sale(message)
    
    elif intent == 'register_client':
        return handle_register_client(message)
    
    elif intent == 'register_product':
        return handle_register_product(message)
    
    elif intent == 'list_products':
        return handle_list_products()
    
    elif intent == 'check_debt':
        return handle_check_debt(msg_lower)
    
    elif intent == 'client_history':
        return handle_client_history(msg_lower)
    
    elif intent == 'sales_today':
        return handle_sales_today()
    
    elif intent == 'sales_month':
        return handle_sales_month()
    
    elif intent == 'report':
        return handle_report()
    
    elif intent == 'list_clients':
        return handle_list_clients()
    
    elif intent == 'help':
        return handle_help()
    
    else:
        response_text = chat_service.chat(message, [])
        return {'message': response_text, 'action': None}


def extract_client_name(msg_lower):
    patterns = [
        r'para\s+(?:o\s+)?(\w+)',
        r'pro\s+(\w+)',
        r'cliente\s+(\w+)',
        r'vendi\s+(?:.*?)\s+para\s+(?:o\s+)?(\w+)',
        r'vendi\s+(\w+)',
        r'de\s+(\w+)',
        r'ao\s+(\w+)',
        r'foi\s+vendido\s+(?:.*?)\s+para\s+(?:o\s+)?(\w+)',
        r'vendeu\s+(?:.*?)\s+para\s+(?:o\s+)?(\w+)',
        r'teve\s+(?:.*?)\s+para\s+(?:o\s+)?(\w+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, msg_lower)
        if match:
            name = match.group(1)
            # Ignorar palavras que não são nomes
            if name.lower() not in ['hoje', 'ontem', 'agora', 'aqui', 'loja', 'casa', 'quanto', 'que']:
                return name.title()
    return None


def handle_create_sale(message):
    msg_lower = message.lower()
    
    # Extrair informações da mensagem
    quantity_match = re.search(r'(\d+)\s*(?:un|x|unidades?|peças?|cps?)', msg_lower)
    quantity = int(quantity_match.group(1)) if quantity_match else 1
    
    paid_match = re.search(r'(?:pago|pagou|recebi)\s*(?:R?\$?\s*)?(\d+(?:[.,]\d{2})?)', msg_lower)
    paid_amount = float(paid_match.group(1).replace(',', '.')) if paid_match else None
    
    # Detectar produto - mapa de sinônimos
    product_map = {
        'cueca': 'cueca', 'cuecas': 'cueca', 'calção': 'cueca', 'calções': 'cueca',
        'calcinha': 'calcinha', 'calcinhas': 'calcinha',
        'sutiã': 'sutiã', 'sutia': 'sutiã', 'sutiens': 'sutiã', 'sutias': 'sutiã',
        'lingerie': 'lingerie',
        'conjunto': 'conjunto', 'conjuntos': 'conjunto',
        'body': 'body', 'bodies': 'body',
        'pijama': 'pijama', 'pijamas': 'pijama',
        'meia': 'meia', 'meias': 'meia',
    }
    
    product_name = None
    for keyword, normalized in product_map.items():
        if keyword in msg_lower:
            product_name = normalized
            break
    
    # Extrair nome do cliente
    client_name = extract_client_name(msg_lower)
    
    # Agora verificar o que temos e tomar ação
    has_product = product_name is not None
    has_client = client_name is not None
    has_quantity = quantity > 0
    
    # Se falta cliente, perguntar
    if not has_client:
        if has_product:
            return {'message': "Qual é o nome do cliente?", 'action': 'ask_client'}
        else:
            return {'message': "Para criar uma venda, me diga: o que vendeu e para quem?", 'action': 'ask_both'}
    
    # Buscar ou criar cliente
    client = Client.objects.filter(name__icontains=client_name).first()
    if not client:
        phone_match = re.search(r'(\d{10,11})', message)
        phone = phone_match.group(1) if phone_match else '00000000000'
        client = Client.objects.create(name=client_name, whatsapp=phone)
    
    # Se falta produto, perguntar
    if not has_product:
        return {'message': f"Para {client.name}, qual produto foi vendido?", 'action': 'ask_product', 'client_id': str(client.id)}
    
    # Buscar produto
    product = Product.objects.filter(name__icontains=product_name, active=True).first()
    
    if not product:
        return {'message': f"Produto '{product_name}' não encontrado no catálogo. O que mais ela levou?", 'action': 'ask_product', 'client_id': str(client.id)}
    
    # Tudo ok, criar venda!
    total = float(product.price) * quantity
    
    if paid_amount is not None:
        if paid_amount >= total:
            status = 'paid'
        elif paid_amount > 0:
            status = 'partial'
        else:
            status = 'pending'
    else:
        status = 'pending'
    
    sale = Sale.objects.create(
        client=client,
        products=[{'id': str(product.id), 'name': product.name, 'price': float(product.price), 'quantity': quantity}],
        total=total,
        paid_amount=paid_amount if paid_amount else 0,
        status=status,
        commission=total * 0.35,
        profit=total - (float(product.cost or 0) * quantity),
        payment_type='cash'
    )
    
    product.stock -= quantity
    product.save()
    
    msg = f"✅ Venda registrada!\n\n👤 Cliente: {client.name}\n📦 Produto: {product.name} x{quantity}\n💰 Total: R$ {total:.2f}\n"
    if paid_amount:
        msg += f"💵 Pago: R$ {paid_amount:.2f}\n"
    msg += f"Status: {'Pago' if status == 'paid' else 'Pendente'}"
    
    return {'message': msg, 'action': 'sale_created', 'sale_id': str(sale.id)}


def handle_register_client(message):
    msg_lower = message.lower()
    
    patterns = [
        r'cadastrar\s+(?:cliente\s+)?(\w+)',
        r'cliente\s+(\w+)',
        r'novo\s+cliente\s+(\w+)',
        r'criar\s+cliente\s+(\w+)',
    ]
    
    client_name = None
    for pattern in patterns:
        match = re.search(pattern, msg_lower)
        if match:
            client_name = match.group(1).title()
            break
    
    if not client_name:
        name_match = re.search(r'(\w+)\s+(?:com|whatsapp)?\s*(\d{10,11})?', message)
        if name_match:
            client_name = name_match.group(1).title()
    
    if client_name:
        existing = Client.objects.filter(name__icontains=client_name).first()
        if existing:
            return {
                'message': f"Cliente '{existing.name}' já existe! WhatsApp: {existing.whatsapp}",
                'action': 'client_exists'
            }
        
        phone_match = re.search(r'(\d{10,11})', message)
        phone = phone_match.group(1) if phone_match else '00000000000'
        
        client = Client.objects.create(name=client_name, whatsapp=phone)
        return {
            'message': f"✅ Cliente '{client.name}' criado!\nWhatsApp: {client.whatsapp}",
            'action': 'client_created'
        }
    
    return {
        'message': "Para cadastrar um cliente, me passe o nome. Ex: 'cadastra cliente Maria'",
        'action': 'ask_client_name'
    }


def handle_register_product(message):
    msg_lower = message.lower()
    
    name_match = re.search(r'(?:produto|peça|item)\s+(?:chamado|chamada|é|chama)?\s+(\w+)', msg_lower)
    if not name_match:
        name_match = re.search(r'(\w+)\s+(?:de|por|kgs?|reais?| reais)', msg_lower)
    
    price_match = re.search(r'(?:R?\$?\s*)?(\d+(?:[.,]\d{2})?)', message)
    
    if name_match and price_match:
        product_name = name_match.group(1).title()
        price = float(price_match.group(1).replace(',', '.'))
        
        product = Product.objects.create(
            name=product_name,
            category='lingerie',
            price=price,
            stock=0
        )
        
        return {
            'message': f"✅ Produto '{product.name}' criado!\nPreço: R$ {price:.2f}",
            'action': 'product_created'
        }
    
    return {
        'message': "Para criar um produto, me passe o nome e o preço. Ex: 'criar produto Calcinha 25'",
        'action': 'ask_product_info'
    }


def handle_list_products():
    products = Product.objects.filter(active=True, stock__gt=0).order_by('name')
    
    if not products.exists():
        return {'message': "Nenhum produto disponível no momento.", 'action': None}
    
    msg = "📦 *PRODUTOS DISPONÍVEIS*\n\n"
    for p in products:
        msg += f"• {p.name} ({p.size or 'UN'}) - R$ {p.price:.2f}\n"
    
    msg += f"\nTotal: {products.count()} produtos"
    
    return {'message': msg, 'action': None}


def handle_check_debt(msg_lower):
    client_name = extract_client_name(msg_lower)
    
    if not client_name:
        return {
            'message': "Qual o nome do cliente para verificar pendências?",
            'action': 'ask_client'
        }
    
    client = Client.objects.filter(name__icontains=client_name).first()
    if not client:
        return {'message': f"Cliente '{client_name}' não encontrado.", 'action': None}
    
    pending = Sale.objects.filter(
        client=client,
        status__in=['pending', 'partial', 'overdue']
    ).order_by('-created_at')
    
    if pending.exists():
        msg = f"📋 *Pendências de {client.name}*\n\n"
        total_pending = 0
        for s in pending:
            p = float(s.total - s.paid_amount)
            total_pending += p
            days = (timezone.now().date() - s.created_at.date()).days
            msg += f"• {s.created_at.strftime('%d/%m')}: R$ {p:.2f}"
            if s.status == 'overdue':
                msg += f" ⚠️ Atrasado({days}d)"
            msg += "\n"
        msg += f"\n*Total pendente: R$ {total_pending:.2f}*"
    else:
        msg = f"✅ {client.name} está em dia! Nenhuma pendência."
    
    return {'message': msg, 'action': None}


def handle_client_history(msg_lower):
    client_name = extract_client_name(msg_lower)
    
    if not client_name:
        return {'message': "De qual cliente você quer ver o histórico?", 'action': 'ask_client'}
    
    client = Client.objects.filter(name__icontains=client_name).first()
    if not client:
        return {'message': f"Cliente '{client_name}' não encontrado.", 'action': None}
    
    sales = Sale.objects.filter(client=client).exclude(status='canceled').order_by('-created_at')[:10]
    
    if not sales.exists():
        return {'message': f"{client.name} não tem compras registradas.", 'action': None}
    
    msg = f"📊 *Histórico de {client.name}*\n\n"
    total = 0
    paid = 0
    
    for s in sales:
        total += float(s.total)
        paid += float(s.paid_amount)
        status_emoji = "✅" if s.status == 'paid' else "⏳" if s.status == 'partial' else "❌"
        msg += f"{status_emoji} {s.created_at.strftime('%d/%m/%Y')} - R$ {s.total:.2f} ({s.get_status_display()})\n"
    
    msg += f"\nTotal compras: R$ {total:.2f}"
    msg += f"\nTotal pago: R$ {paid:.2f}"
    msg += f"\nPendente: R$ {total - paid:.2f}"
    
    return {'message': msg, 'action': None}


def handle_sales_today():
    today = timezone.now().date()
    
    sales = Sale.objects.filter(created_at__date=today).exclude(status='canceled')
    
    if not sales.exists():
        return {'message': "Nenhuma venda hoje.", 'action': None}
    
    total = sum(float(s.total) for s in sales)
    paid = sales.filter(status='paid').count()
    pending = sales.exclude(status='paid').count()
    
    msg = f"📈 *Vendas de Hoje ({today.strftime('%d/%m')})*\n\n"
    msg += f"Total: R$ {total:.2f}\n"
    msg += f"Pagas: {paid}\n"
    msg += f"Pendentes: {pending}\n"
    msg += f"\nÚltimas vendas:\n"
    
    for s in sales[:5]:
        client = s.client.name if s.client else "Consumidor"
        msg += f"• {client}: R$ {s.total:.2f} - {s.get_status_display()}\n"
    
    return {'message': msg, 'action': None}


def handle_sales_month():
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    sales = Sale.objects.filter(created_at__gte=month_start).exclude(status='canceled')
    
    if not sales.exists():
        return {'message': "Nenhuma venda este mês.", 'action': None}
    
    total = sum(float(s.total) for s in sales)
    paid_count = sales.filter(status='paid').count()
    pending_count = sales.exclude(status='paid').count()
    commission = total * 0.35
    profit = sum(float(s.profit) for s in sales)
    
    msg = f"📈 *Vendas do Mês ({now.strftime('%m/%Y')})*\n\n"
    msg += f"Total: R$ {total:.2f}\n"
    msg += f"Vendas: {sales.count()}\n"
    msg += f"Pagas: {paid_count}\n"
    msg += f"Pendentes: {pending_count}\n"
    msg += f"\nComissão: R$ {commission:.2f}\n"
    msg += f"Lucro: R$ {profit:.2f}"
    
    return {'message': msg, 'action': None}


def handle_report():
    now = timezone.now()
    today = now.date()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    today_sales = Sale.objects.filter(created_at__date=today).exclude(status='canceled')
    month_sales = Sale.objects.filter(created_at__gte=month_start).exclude(status='canceled')
    
    debtors = Client.objects.filter(total_due__gt=0)
    
    today_total = sum(float(s.total) for s in today_sales)
    month_total = sum(float(s.total) for s in month_sales)
    total_debt = sum(float(c.total_due) for c in debtors)
    month_profit = sum(float(s.profit) for s in month_sales)
    
    msg = f"📊 *RELATÓRIO GERAL*\n\n"
    msg += f"📅 *Hoje:*\nR$ {today_total:.2f} ({today_sales.count()} vendas)\n\n"
    msg += f"📆 *Este Mês:*\nR$ {month_total:.2f} ({month_sales.count()} vendas)\n"
    msg += f"Lucro: R$ {month_profit:.2f}\n\n"
    msg += f"💸 *Pendências:*\nR$ {total_debt:.2f} ({debtors.count()} clientes)"
    
    return {'message': msg, 'action': None}


def handle_list_clients():
    clients = Client.objects.all().order_by('name')[:20]
    
    if not clients.exists():
        return {'message': "Nenhum cliente cadastrado.", 'action': None}
    
    msg = f"👥 *CLIENTES ({clients.count()})*\n\n"
    for c in clients:
        due = float(c.total_due)
        if due > 0:
            msg += f"• {c.name} - Devendo R$ {due:.2f}\n"
        else:
            msg += f"• {c.name}\n"
    
    return {'message': msg, 'action': None}


def handle_help():
    msg = "*AJUDA - Comandos disponiveis*\n\n*Produtos:*\n- lista produtos - ver produtos\n- cadastra produto [nome] [preco]\n\n*Clientes:*\n- lista clientes - ver todos\n- cadastra cliente [nome] [whatsapp]\n- [cliente] deve quanto? - verificar divida\n\n*Vendas:*\n- vendi para [cliente] [produto] - criar venda\n- historico de [cliente] - ver compras\n\n*Relatorios:*\n- vendas hoje - vendas do dia\n- vendas do mes - vendas do mes\n- relatorio - resumo geral\n\nE so digitar o comando ou perguntar!"

    return {'message': msg, 'action': None}


@login_required
def chat_settings(request):
    if not request.user.is_superuser:
        from django.http import Http404
        raise Http404("Página não encontrada")
    
    ai_settings = AISettings.objects.all()
    active = AISettings.get_active()
    
    if request.method == 'POST':
        name = request.POST.get('name', 'Chat IA')
        model = request.POST.get('model', 'gpt-4o-mini')
        provider = request.POST.get('provider', 'openai')
        api_key = request.POST.get('api_key', '').strip()
        api_url = request.POST.get('api_url', 'https://api.openai.com/v1/chat/completions')
        system_prompt = request.POST.get('system_prompt', '')
        active_flag = request.POST.get('active') == 'on'
        
        if active:
            active.name = name
            active.model = model
            active.provider = provider
            active.api_key = api_key
            active.api_url = api_url
            active.system_prompt = system_prompt
            active.active = active_flag
            active.save()
        else:
            AISettings.objects.create(
                name=name, model=model, provider=provider, api_key=api_key,
                api_url=api_url, system_prompt=system_prompt, active=active_flag
            )
        
        return render(request, 'chat/settings.html', {
            'ai_settings': ai_settings, 'active': active, 'saved': True
        })
    
    return render(request, 'chat/settings.html', {
        'ai_settings': ai_settings, 'active': active
    })