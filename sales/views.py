from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
import json
from .models import Sale
from clients.models import Client
from products.models import Product
from core.models import Settings
from core.whatsapp_bot import send_whatsapp_message


def send_sale_receipt(client, sale):
    """Envia mensagem de recibo após venda"""
    if not client or not client.whatsapp:
        return None
    
    from core.models import Settings
    pix_key = Settings.get('pix_key', '')
    
    items_text = ""
    for p in sale.products:
        try:
            product = Product.objects.get(pk=p['id'])
            items_text += f"- {product.name} x{p['quantity']}\n"
        except:
            pass
    
    total = float(sale.total)
    paid = float(sale.paid_amount)
    remaining = total - paid
    
    if sale.status == 'paid':
        message = f"Ola {client.name.split()[0]}! Obrigado pela preferencia!\n\nRecibo:\n{items_text}\nTotal: R$ {total:.2f}\nPagamento: PAGO"
    else:
        pix_info = f"\nPIX: {pix_key}" if pix_key else ""
        message = f"Ola {client.name.split()[0]}! Voce tem uma compra pendente de R$ {remaining:.2f}.\n\nItens:\n{items_text}\nTotal: R$ {total:.2f}\nPago: R$ {paid:.2f}\nRestante: R$ {remaining:.2f}{pix_info}\n\nQuando puder, nos mande uma mensagem para combinar o pagamento!"
    
    return send_whatsapp_message(client.whatsapp, message)


@login_required
def sales_list(request):
    status_filter = request.GET.get('status', 'all')
    
    if status_filter == 'canceled':
        sales_qs = Sale.objects.filter(status='canceled')
    elif status_filter == 'pending':
        sales_qs = Sale.objects.exclude(status='canceled').filter(status__in=['pending', 'partial', 'overdue'])
    elif status_filter == 'paid':
        sales_qs = Sale.objects.exclude(status='canceled').filter(status='paid')
    else:
        sales_qs = Sale.objects.all()
    
    sales = list(sales_qs[:20])
    
    now = timezone.now()
    today = now.date()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    total_today = sales_qs.filter(created_at__date=today).aggregate(Sum('total'))['total__sum'] or 0
    total_month = Sale.objects.exclude(status='canceled').filter(created_at__gte=month_start).aggregate(Sum('total'))['total__sum'] or 0
    
    commission_rate = float(Settings.get('commission_rate', settings.COMISSION_RATE * 100)) / 100
    commission_month = float(total_month) * commission_rate
    
    pending_sales = Sale.objects.exclude(status='canceled').filter(status__in=['pending', 'partial', 'overdue'])
    total_pending = sum(float(s.total - s.paid_amount) for s in pending_sales)
    pending_count = pending_sales.count()
    
    return render(request, 'sales/list.html', {
        'sales': sales,
        'total_today': total_today,
        'total_month': total_month,
        'commission_month': commission_month,
        'total_pending': total_pending,
        'pending_count': pending_count,
        'status_filter': status_filter,
    })


@login_required
def new_sale(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        
        client_id = data.get('client_id')
        products_data = data.get('products', [])
        payment_type = data.get('payment_type', 'cash')
        paid_amount = float(data.get('paid_amount', 0))
        
        if not products_data:
            return JsonResponse({'error': 'Nenhum produto selecionado'}, status=400)
        
        if not client_id:
            return JsonResponse({'error': 'Selecione um cliente'}, status=400)
        
        client = None
        if client_id:
            client = Client.objects.get(pk=client_id)
        
        total = 0
        cost = 0
        for p in products_data:
            product = Product.objects.get(pk=p['id'])
            qty = p['quantity']
            total += float(product.price) * qty
            cost += float(product.cost or 0) * qty
        
        commission_rate = float(Settings.get('commission_rate', settings.COMISSION_RATE * 100)) / 100
        profit = total - cost
        commission = total * commission_rate
        
        if paid_amount >= total:
            status = 'paid'
        elif paid_amount > 0:
            status = 'partial'
        else:
            status = 'pending'
        
        sale = Sale.objects.create(
            client=client,
            products=products_data,
            total=total,
            paid_amount=paid_amount,
            status=status,
            commission=commission,
            profit=profit,
            payment_type=payment_type,
        )
        
        for p in products_data:
            try:
                product = Product.objects.get(pk=p['id'])
                product.stock -= p['quantity']
                product.save()
            except Product.DoesNotExist:
                pass
        
        if client:
            due_amount = sum(
                float(s.total - s.paid_amount) 
                for s in Sale.objects.filter(client=client).exclude(status__in=['paid', 'canceled'])
            )
            client.total_due = due_amount
            client.last_purchase = timezone.now()
            client.save()
            
            result = send_sale_receipt(client, sale)
            whatsapp_link = result.get('link', '') if result else ''
        else:
            whatsapp_link = ''
        
        return JsonResponse({'id': str(sale.id), 'success': True, 'whatsapp_link': whatsapp_link})
    
    products = Product.objects.filter(active=True, stock__gt=0)
    clients = Client.objects.all()
    
    return render(request, 'sales/new.html', {
        'products': products,
        'clients': clients,
    })


@login_required
def sale_detail(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    return render(request, 'sales/detail.html', {'sale': sale})


@login_required
def receive_payment(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    
    if request.method == 'POST':
        amount = Decimal(str(request.POST.get('amount', 0)))
        sale.paid_amount += amount
        
        if sale.paid_amount >= sale.total:
            sale.status = 'paid'
        else:
            sale.status = 'partial'
        
        sale.save()
        
        if sale.client:
            due = sum(
                float(s.total - s.paid_amount)
                for s in Sale.objects.filter(client=sale.client).exclude(status__in=['paid', 'canceled'])
            )
            sale.client.total_due = due
            sale.client.save()
        
        messages.success(request, 'Pagamento registrado!')
        return redirect('sale_detail', pk=pk)
    
    return render(request, 'sales/payment.html', {
        'sale': sale,
        'pending_amount': float(sale.pending_amount)
    })


@login_required
def sale_delete(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    sale.delete()
    messages.success(request, 'Venda excluída!')
    return redirect('sales_list')


@login_required
@require_http_methods(["POST"])
def cancel_sale(request, pk):
    """Cancela uma venda e restaura o estoque"""
    sale = get_object_or_404(Sale, pk=pk)
    
    # Restaurar estoque
    for p in sale.products:
        try:
            product = Product.objects.get(pk=p['id'])
            product.stock += p['quantity']
            product.save()
        except Product.DoesNotExist:
            pass
    
    # Atualizar total devido do cliente
    if sale.client:
        due_amount = sum(
            float(s.total - s.paid_amount) 
            for s in Sale.objects.filter(client=sale.client).exclude(status__in=['paid', 'canceled']).exclude(pk=pk)
        )
        sale.client.total_due = due_amount
        sale.client.save()
    
    # Marcar como cancelado (não excluir)
    sale.status = 'canceled'
    sale.save()
    
    messages.success(request, 'Venda cancelada e estoque restaurado!')
    return redirect('sales_list')


@login_required
def quick_stats(request):
    today = timezone.now().date()
    month_start = today.replace(day=1)
    
    sales = Sale.objects.filter(created_at__date=today)
    month = Sale.objects.filter(created_at__date__gte=month_start)
    
    data = {
        'today_total': float(sales.aggregate(Sum('total'))['total__sum'] or 0),
        'today_count': sales.count(),
        'month_total': float(month.aggregate(Sum('total'))['total__sum'] or 0),
        'month_commission': float(month.aggregate(Sum('commission'))['commission__sum'] or 0),
    }
    
    return JsonResponse(data)