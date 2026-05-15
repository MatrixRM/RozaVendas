# -*- coding: utf-8 -*-
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from clients.models import Client
from core.models import WhatsAppMessage, WhatsAppTemplate
from sales.models import Sale
from core.whatsapp_bot import send_whatsapp_message


def build_collection_message(client):
    """Constrói mensagem de cobrança com detalhes das vendas pendentes"""
    from sales.models import Sale
    
    name = client.name.split()[0]
    sales = Sale.objects.filter(
        client=client,
        status__in=['pending', 'partial', 'overdue']
    ).order_by('-created_at')
    
    if not sales:
        return f"Olá {name}! Você está em dia conosco! 😊"
    
    message = f"Olá {name}!\n\n📋 Resumo das suas compras pendentes:\n\n"
    
    total_pending = 0
    for sale in sales:
        pending = float(sale.total - sale.paid_amount)
        total_pending += pending
        date = sale.created_at.strftime('%d/%m/%Y')
        
        message += f"• Compra {date}: R$ {sale.total:.2f} | Pago: R$ {sale.paid_amount:.2f} | Pendente: R$ {pending:.2f}\n"
        
        items = sale.get_products_list()
        if items:
            item_names = ", ".join([f"{i.get('quantity', 1)}x {i.get('name', 'Item')}" for i in items[:3]])
            message += f"  Itens: {item_names}\n"
        
        if sale.status == 'overdue':
            days = sale.days_overdue
            message += f"  ⚠️ ATRASADO há {days} dias\n"
        
        message += "\n"
    
    message += f"💰 Total pendente: R$ {total_pending:.2f}\n\n"
    message += "Quando puder, nos mande uma mensagem para combinar o pagamento!"
    
    return message


def build_receipt_message(client, sale=None):
    """Constrói mensagem de recibo detalhada"""
    if sale:
        items = sale.get_products_list()
        items_text = "\n".join([f"  • {i.get('quantity', 1)}x {i.get('name', 'Item')} - R$ {i.get('subtotal', 0):.2f}" for i in items]) if items else "  Produtos diversos"
        
        message = f"🧾 RECIBO - Compra {sale.created_at.strftime('%d/%m/%Y')}\n\n"
        message += f"{items_text}\n\n"
        message += f"Total: R$ {sale.total:.2f}\n"
        message += f"Pago: R$ {sale.paid_amount:.2f}\n"
        message += f"Troco: R$ {(float(sale.paid_amount) - float(sale.total)):.2f}\n\n"
        message += f"Obrigado pela preferência, {client.name.split()[0]}! 😊"
        return message
    
    all_paid = Sale.objects.filter(client=client, status='paid').order_by('-created_at')[:5]
    if not all_paid:
        return f"Ola {client.name.split()[0]}! Obrigado pela preferencia!"
    
    message = f"Ola {client.name.split()[0]}! Obrigado pela preferencia! 😊\n\n"
    message += "Suas compras quitadas:\n\n"
    
    total_paid = 0
    for s in all_paid:
        total_paid += float(s.total)
        message += f"• {s.created_at.strftime('%d/%m')}: R$ {s.total:.2f} ✅\n"
    
    message += f"\nTotal: R$ {total_paid:.2f}"
    message += "\n\n esperamos voce novamente em breve!"
    
    return message


TEMPLATES = {
    'reminder': "Olá {name}!\n\nTemos produtos esperando por você! Que tal dar uma olhadinha nas novas?",
    
    'collection': build_collection_message,
    
    'weekly': "Olá {name}!\n\nEssa semana temos promoções especiais!\n\nVenha nos visitar!",
    
    'thanks': build_receipt_message,
    
    'overdue': build_collection_message,
}


def format_whatsapp_link(whatsapp, message):
    phone = ''.join(filter(str.isdigit, whatsapp))
    message = message.replace('\n', '%0A')
    return f"https://wa.me/{phone}?text={message}"


@login_required
def whatsapp_panel(request):
    templates = WhatsAppTemplate.objects.filter(active=True)
    
    debtors = Client.objects.filter(total_due__gt=0)
    
    return render(request, 'core/whatsapp.html', {
        'templates': templates,
        'debtors': debtors,
    })


@login_required
def send_whatsapp(request, client_id):
    if request.method == 'POST':
        from core.models import Settings
        client = Client.objects.get(pk=client_id)
        message_type = request.POST.get('message_type', 'reminder')
        
        client_sales = Sale.objects.filter(client=client, status__in=['pending', 'partial', 'overdue'])
        pending_amount = sum(float(s.total - s.paid_amount) for s in client_sales)
        
        if pending_amount <= 0:
            message_type = 'thanks'
        
        pix_key = Settings.get('pix_key', '')
        
        template = TEMPLATES.get(message_type, TEMPLATES['reminder'])
        
        if callable(template):
            if message_type == 'thanks':
                message = template(client)
            else:
                message = template(client)
                if pix_key:
                    message += f"\n\nPIX para pagamento: {pix_key}"
        else:
            message = template.format(
                name=client.name.split()[0],
                amount=f"{pending_amount:.2f}".replace('.', ','),
                days=(timezone.now().date() - client.last_purchase.date()).days if client.last_purchase else 0
            )
            if pix_key and pending_amount > 0:
                message += f"\n\nPIX para pagamento: {pix_key}"
        
        result = send_whatsapp_message(client.whatsapp, message)
        
        WhatsAppMessage.objects.create(
            client=client,
            message_type=message_type,
            message=message,
            sent=False,
            sent_at=timezone.now()
        )
        
        return JsonResponse({
            'success': True,
            'link': result['link'],
            'message': message,
            'type': 'link'
        })
    
    return JsonResponse({'error': 'Método inválido'}, status=400)


@login_required
def bulk_whatsapp(request):
    if request.method == 'POST':
        message_type = request.POST.get('message_type')
        days = int(request.POST.get('days', 7))
        
        debtors = Client.objects.filter(total_due__gt=0)
        
        from core.models import Settings
        pix_key = Settings.get('pix_key', '')
        
        links = []
        for client in debtors:
            template = TEMPLATES.get(message_type, TEMPLATES['collection'])
            
            if callable(template):
                message = template(client)
                if pix_key and message_type in ['collection', 'overdue']:
                    message += f"\n\nPIX para pagamento: {pix_key}"
            else:
                pending = float(client.total_due)
                message = template.format(
                    name=client.name.split()[0],
                    amount=f"{pending:.2f}".replace('.', ','),
                    days=days
                )
                if pix_key and pending > 0:
                    message += f"\n\nPIX para pagamento: {pix_key}"
            
            links.append({
                'client': client.name,
                'whatsapp': client.whatsapp,
                'link': format_whatsapp_link(client.whatsapp, message)
            })
        
        return JsonResponse({'links': links})
    
    return JsonResponse({'error': 'Método inválido'}, status=400)


PROMO_TEMPLATES = [
    "Olá! Chegaram novas peças lindas na nossa loja. Venha conferir!",
    "Olá! Temos novidades super bonitas esperando por você. Que tal dar uma passadinha?",
    "Olá! Novas peças chegaram! Venha ver as tendências da temporada.",
    "Olá! Preparamos peças especiais para você. Visite-nos!",
    "Olá! Que tal um look novo? Novidades acabaram de chegar!",
    "Olá! Sua clientesVIP tem novidades imperdíveis. Venha ver!",
    "Olá! Novas peças chegaram para renovar seu guarda-roupa. Estamos te esperando!",
    "Olá! Especialmente para você: novidades fresquinhas!",
]


@login_required
def send_promotion(request):
    """Envia promoção para todos os clientes"""
    if request.method == 'POST':
        message = request.POST.get('message', '').strip()
        
        if not message:
            messages.error(request, 'Digite uma mensagem!')
            return redirect('settings')
        
        clients = Client.objects.filter(whatsapp__isnull=False).exclude(whatsapp='')
        
        count = 0
        for client in clients:
            result = send_whatsapp_message(client.whatsapp, message)
            if result.get('link'):
                count += 1
                WhatsAppMessage.objects.create(
                    client=client,
                    message_type='weekly',
                    message=message,
                    sent=False,
                    sent_at=timezone.now()
                )
        
        messages.success(request, f'Mensagem preparada para {count} clientes!')
        return redirect('settings')
    
    return redirect('settings')


@login_required
def random_promotion(request):
    """Prepara mensagem aleatória para todos os clientes"""
    import random
    message = random.choice(PROMO_TEMPLATES)
    
    clients = Client.objects.filter(whatsapp__isnull=False).exclude(whatsapp='')
    
    links = []
    for client in clients:
        result = send_whatsapp_message(client.whatsapp, message)
        if result.get('link'):
            links.append({
                'name': client.name,
                'whatsapp': client.whatsapp,
                'link': result['link']
            })
            WhatsAppMessage.objects.create(
                client=client,
                message_type='weekly',
                message=message,
                sent=False,
                sent_at=timezone.now()
            )
    
    request.session['promo_links'] = links
    request.session['promo_message'] = message
    return redirect('promo_preview')


@login_required
def promo_preview(request):
    """Mostra os links para envio"""
    links = request.session.get('promo_links', [])
    message = request.session.get('promo_message', '')
    
    if not links:
        messages.warning(request, 'Nenhum cliente com WhatsApp encontrado!')
        return redirect('settings')
    
    return render(request, 'core/promo_preview.html', {
        'links': links,
        'message': message
    })


@login_required
def send_custom_promotion(request):
    """Prepara mensagem customizada para todos os clientes"""
    message = request.POST.get('message', '').strip()
    
    if not message:
        messages.error(request, 'Digite uma mensagem!')
        return redirect('settings')
    
    clients = Client.objects.filter(whatsapp__isnull=False).exclude(whatsapp='')
    
    links = []
    for client in clients:
        result = send_whatsapp_message(client.whatsapp, message)
        if result.get('link'):
            links.append({
                'name': client.name,
                'whatsapp': client.whatsapp,
                'link': result['link']
            })
            WhatsAppMessage.objects.create(
                client=client,
                message_type='weekly',
                message=message,
                sent=False,
                sent_at=timezone.now()
            )
    
    request.session['promo_links'] = links
    request.session['promo_message'] = message
    return redirect('promo_preview')


@login_required
def settings_view(request):
    if request.method == 'POST':
        from core.models import Settings
        commission = request.POST.get('commission_rate')
        pix_key = request.POST.get('pix_key')
        overdue_days = request.POST.get('overdue_days')
        profit_margin = request.POST.get('profit_margin')
        min_stock = request.POST.get('min_stock')
        
        if commission:
            Settings.set('commission_rate', commission, 'Taxa de comissão')
        if pix_key:
            Settings.set('pix_key', pix_key, 'Chave PIX para cobranças')
        if overdue_days:
            Settings.set('overdue_days', overdue_days, 'Dias para considerar atraso')
        if profit_margin:
            Settings.set('profit_margin', profit_margin, 'Margem de lucro (%)')
        if min_stock:
            Settings.set('min_stock', min_stock, 'Estoque mínimo para alerta')
        
        messages.success(request, 'Configuração salva!')
    
    from core.models import Settings
    commission = Settings.get('commission_rate', '35')
    pix_key = Settings.get('pix_key', '')
    overdue_days = Settings.get('overdue_days', '7')
    profit_margin = Settings.get('profit_margin', '5')
    min_stock = Settings.get('min_stock', '5')
    
    return render(request, 'core/settings.html', {
        'commission': commission,
        'pix_key': pix_key,
        'overdue_days': overdue_days,
        'profit_margin': profit_margin,
        'min_stock': min_stock
    })


@login_required
def api_check_debtors(request):
    from django.utils import timezone
    from datetime import timedelta
    
    days = int(request.GET.get('days', 7))
    cutoff = timezone.now() - timedelta(days=days)
    
    debtors = Client.objects.filter(
        total_due__gt=0,
        last_purchase__lt=cutoff
    ).values('id', 'name', 'whatsapp', 'total_due', 'last_purchase')
    
    return JsonResponse(list(debtors), safe=False)