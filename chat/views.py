import re
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Sum
from django.conf import settings
from clients.models import Client
from products.models import Product
from sales.models import Sale
from .models import AISettings
from .service import get_chat_service


@login_required
def chat_home(request):
    return render(request, 'chat/home.html')


@login_required
@require_http_methods(["POST"])
def chat_message(request):
    message = request.POST.get('message', '').strip()
    
    if not message:
        return JsonResponse({'error': 'Mensagem vazia'}, status=400)
    
    chat_service = get_chat_service()
    
    if chat_service:
        intent = chat_service.extract_intent(message)
        response = process_intent(intent, message, chat_service)
        return JsonResponse(response)
    else:
        return JsonResponse({
            'message': "Configure o Chat IA em Configurações para usar recursos avançados.",
            'action': None
        })


def process_intent(intent, message, chat_service):
    """Processa a intenção do usuário e retorna a resposta"""
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
        r'para\s+(\w+)',
        r'cliente\s+(\w+)',
        r'vendi\s+(?:.*?)\s+para\s+(\w+)',
        r'vendi\s+(\w+)',
        r'de\s+(\w+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, msg_lower)
        if match:
            return match.group(1).title()
    return None


def handle_create_sale(message):
    msg_lower = message.lower()
    sale_data = {'detected': False}
    
    product_match = re.search(r'(calcinha|sutien|cueca|lingerie|bodies|meia|conjunto|pijama|calça|blusa)', msg_lower)
    quantity_match = re.search(r'(\d+)\s*(?:un|x|unidades?)', msg_lower)
    client_name = extract_client_name(msg_lower)
    
    if product_match:
        sale_data['detected'] = True
        sale_data['product'] = product_match.group(1).title()
        sale_data['quantity'] = int(quantity_match.group(1)) if quantity_match else 1
    
    if client_name:
        client = Client.objects.filter(name__icontains=client_name).first()
        if not client:
            phone_match = re.search(r'(\d{10,11})', message)
            phone = phone_match.group(1) if phone_match else '00000000000'
            client = Client.objects.create(name=client_name, phone=phone, whatsapp=phone)
        
        if sale_data['detected']:
            product_name = sale_data['product']
            product = Product.objects.filter(name__icontains=product_name, active=True).first()
            
            if product:
                total = float(product.price) * sale_data['quantity']
                paid_match = re.search(r'(?:pago|pagou|recebi)\s*(?:R?\$?\s*)?(\d+(?:[.,]\d{2})?)', msg_lower)
                paid_amount = float(paid_match.group(1).replace(',', '.')) if paid_match else 0
                
                if paid_amount >= total:
                    status = 'paid'
                elif paid_amount > 0:
                    status = 'partial'
                else:
                    status = 'pending'
                
                sale = Sale.objects.create(
                    client=client,
                    products=[{'id': str(product.id), 'name': product.name, 'price': float(product.price), 'quantity': sale_data['quantity']}],
                    total=total,
                    paid_amount=paid_amount,
                    status=status,
                    commission=total * 0.35,
                    profit=total - (float(product.cost or 0) * sale_data['quantity']),
                    payment_type='cash'
                )
                
                product.stock -= sale_data['quantity']
                product.save()
                
                msg = f"✅ Venda criada!\n\nCliente: {client.name}\nProduto: {product.name} x{sale_data['quantity']}\nTotal: R$ {total:.2f}\nStatus: {status}"
                return {'message': msg, 'action': 'sale_created', 'sale_id': str(sale.id)}
            else:
                return {'message': f"Produto '{product_name}' não encontrado. Quer que eu abra o formulário de venda?", 'action': 'sale_form'}
        else:
            return {
                'message': f"Encontrei o cliente {client.name}. Qual produto deseja vender?",
                'action': 'ask_product',
                'client_id': str(client.id)
            }
    else:
        return {
            'message': "Para criar uma venda, preciso saber o nome do cliente. Qual é o nome?",
            'action': 'ask_client'
        }


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
        
        client = Client.objects.create(name=client_name, phone=phone, whatsapp=phone)
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
    msg = """📚 *AJUDA - Comandos disponíveis*

📦 *Produtos:*
- "lista produtos" - ver produtos
- "cadastra produto [nome] [preço]"

👥 *Clientes:*
- "lista clientes" - ver todos
- "cadastra cliente [nome] [whatsapp]"
- "[cliente] deve quanto?" - verificar dívida

🛒 *Vendas:*
- "vendi para [cliente] [produto]" - criar venda
- "historico de [cliente]" - ver compras

📊 *Relatórios:*
- "vendas hoje" - vendas do dia
- "vendas do mês" - vendas do mês
- "relatório" - resumo geral

É só digitar o comando ou perguntar! 😊"""

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
        api_key = request.POST.get('api_key', '').strip()
        api_url = request.POST.get('api_url', 'https://api.openai.com/v1/chat/completions')
        system_prompt = request.POST.get('system_prompt', '')
        active_flag = request.POST.get('active') == 'on'
        
        if active:
            active.name = name
            active.model = model
            active.api_key = api_key
            active.api_url = api_url
            active.system_prompt = system_prompt
            active.active = active_flag
            active.save()
        else:
            AISettings.objects.create(
                name=name, model=model, api_key=api_key,
                api_url=api_url, system_prompt=system_prompt, active=active_flag
            )
        
        return render(request, 'chat/settings.html', {
            'ai_settings': ai_settings, 'active': active, 'saved': True
        })
    
    return render(request, 'chat/settings.html', {
        'ai_settings': ai_settings, 'active': active
    })