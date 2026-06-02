from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.db import transaction
from django.conf import settings
from django.utils import timezone
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from .models import Sale
from clients.models import Client
from products.models import Product
from core.models import Settings
from core.whatsapp_bot import send_whatsapp_message


MONEY = Decimal('0.01')
VALID_PAYMENT_TYPES = {choice[0] for choice in Sale.PAYMENT_TYPES}


def money(value):
    try:
        return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0.00')


def normalize_payment_type(value):
    return value if value in VALID_PAYMENT_TYPES else 'cash'


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
        message = f"Ola {client.name.split()[0]}!\n\nObrigado pela sua compra.\n\nRecibo:\n{items_text}\nTotal: R$ {total:.2f}\nPagamento: pago"
    else:
        pix_info = f"\nPIX: {pix_key}" if pix_key else ""
        message = f"Ola {client.name.split()[0]}!\n\nVoce tem uma compra pendente de R$ {remaining:.2f}.\n\nItens:\n{items_text}\nTotal: R$ {total:.2f}\nPago: R$ {paid:.2f}\nRestante: R$ {remaining:.2f}{pix_info}\n\nQuando puder, nos mande uma mensagem para combinar o pagamento."
    
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
    
    today = date.today()
    month_start = today.replace(day=1)
    
    total_today = sales_qs.filter(created_at__date=today).aggregate(Sum('total'))['total__sum'] or 0
    total_month = Sale.objects.exclude(status='canceled').filter(created_at__date__gte=month_start).aggregate(Sum('total'))['total__sum'] or 0
    
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
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Dados inválidos'}, status=400)
        
        client_id = data.get('client_id')
        products_data = data.get('products', [])
        payment_type = normalize_payment_type(data.get('payment_type', 'cash'))
        paid_amount = money(data.get('paid_amount', 0))
        
        if not products_data:
            return JsonResponse({'error': 'Nenhum produto selecionado'}, status=400)
        
        if not client_id:
            return JsonResponse({'error': 'Selecione um cliente'}, status=400)
        
        if paid_amount < 0:
            return JsonResponse({'error': 'Valor pago não pode ser negativo'}, status=400)

        try:
            client = Client.objects.get(pk=client_id)
        except Client.DoesNotExist:
            return JsonResponse({'error': 'Cliente não encontrado'}, status=400)

        cart_quantities = {}
        for item in products_data:
            product_id = str(item.get('id', ''))
            try:
                qty = int(item.get('quantity', 0))
            except (TypeError, ValueError):
                qty = 0
            if qty <= 0:
                return JsonResponse({'error': 'Quantidade inválida no carrinho'}, status=400)
            cart_quantities[product_id] = cart_quantities.get(product_id, 0) + qty

        with transaction.atomic():
            products = {
                str(product.id): product
                for product in Product.objects.select_for_update().filter(id__in=cart_quantities.keys(), active=True)
            }

            if len(products) != len(cart_quantities):
                return JsonResponse({'error': 'Produto não encontrado ou inativo'}, status=400)

            total = Decimal('0.00')
            cost = Decimal('0.00')
            sale_products = []

            for product_id, qty in cart_quantities.items():
                product = products[product_id]
                if qty > product.stock:
                    return JsonResponse({
                        'error': f'Estoque insuficiente para {product.name}. Disponível: {product.stock}'
                    }, status=400)

                unit_price = money(product.price)
                unit_cost = money(product.cost)
                total += unit_price * qty
                cost += unit_cost * qty
                sale_products.append({
                    'id': str(product.id),
                    'name': product.name,
                    'price': float(unit_price),
                    'cost': float(unit_cost),
                    'quantity': qty,
                })

            total = money(total)
            cost = money(cost)
            commission_rate = Decimal(str(Settings.get('commission_rate', settings.COMISSION_RATE * 100))) / Decimal('100')
            profit = money(total - cost)
            commission = money(total * commission_rate)

            if paid_amount >= total:
                status = 'paid'
            elif paid_amount > 0:
                status = 'partial'
            else:
                status = 'pending'

            sale = Sale.objects.create(
                client=client,
                products=sale_products,
                total=total,
                paid_amount=paid_amount,
                status=status,
                commission=commission,
                profit=profit,
                payment_type=payment_type,
            )

            for product_id, qty in cart_quantities.items():
                product = products[product_id]
                product.stock -= qty
                product.save(update_fields=['stock', 'updated_at'])

        client.last_purchase = timezone.now()
        client.save(update_fields=['last_purchase', 'updated_at'])

        result = send_sale_receipt(client, sale)
        whatsapp_link = result.get('link', '') if result else ''
        
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
        amount = money(request.POST.get('amount', 0))
        payment_type = normalize_payment_type(request.POST.get('payment_type', 'cash'))

        if amount <= 0:
            messages.error(request, 'Informe um valor maior que zero.')
            return redirect('receive_payment', pk=pk)

        if amount > sale.pending_amount:
            messages.error(request, 'O pagamento não pode ser maior que o valor pendente.')
            return redirect('receive_payment', pk=pk)
        
        sale.paid_amount += amount
        
        # Atualizar forma de pagamento
        if payment_type != sale.payment_type:
            sale.payment_type = payment_type
        
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
    with transaction.atomic():
        if sale.status != 'canceled':
            for p in sale.get_products_list():
                try:
                    product = Product.objects.select_for_update().get(pk=p['id'])
                    product.stock += int(p.get('quantity', 0))
                    product.save(update_fields=['stock', 'updated_at'])
                except (Product.DoesNotExist, ValueError, TypeError):
                    pass
        sale.delete()
    messages.success(request, 'Venda excluída!')
    return redirect('sales_list')


@login_required
@require_http_methods(["POST"])
def cancel_sale(request, pk):
    """Cancela uma venda e restaura o estoque"""
    sale = get_object_or_404(Sale, pk=pk)

    if sale.status == 'canceled':
        messages.info(request, 'Esta venda já estava cancelada.')
        return redirect('sales_list')
    
    # Restaurar estoque
    with transaction.atomic():
        for p in sale.get_products_list():
            try:
                product = Product.objects.select_for_update().get(pk=p['id'])
                product.stock += int(p.get('quantity', 0))
                product.save(update_fields=['stock', 'updated_at'])
            except (Product.DoesNotExist, ValueError, TypeError):
                pass
        sale.status = 'canceled'
        sale.save(update_fields=['status'])
    
    # Atualizar total devido do cliente
    if sale.client:
        due_amount = sum(
            float(s.total - s.paid_amount) 
            for s in Sale.objects.filter(client=sale.client).exclude(status__in=['paid', 'canceled']).exclude(pk=pk)
        )
        sale.client.total_due = due_amount
        sale.client.save()
    
    # Marcar como cancelado (não excluir)
    messages.success(request, 'Venda cancelada e estoque restaurado!')
    return redirect('sales_list')


@login_required
def quick_stats(request):
    today = date.today()
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
