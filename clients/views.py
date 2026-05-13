from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from .models import Client
from sales.models import Sale


def validate_whatsapp(whatsapp):
    phone = ''.join(filter(str.isdigit, whatsapp))
    return len(phone) >= 10 and len(phone) <= 11


@login_required
def clients_list(request):
    clients = Client.objects.all().order_by('name')
    search = request.GET.get('search', '')
    
    if search:
        clients = clients.filter(name__icontains=search) | clients.filter(whatsapp__icontains=search)
    
    debtors = Client.objects.filter(total_due__gt=0)
    total_debt = debtors.aggregate(Sum('total_due'))['total_due__sum'] or 0
    
    return render(request, 'clients/list.html', {
        'clients': clients,
        'debtors': debtors,
        'total_debt': total_debt,
        'search': search
    })


@login_required
def client_new(request):
    if request.method == 'POST':
        whatsapp = request.POST.get('whatsapp', '')
        
        if not validate_whatsapp(whatsapp):
            messages.error(request, 'WhatsApp inválido! Use formato (00) 00000-0000')
            return render(request, 'clients/form.html')
        
        if Client.objects.filter(whatsapp__icontains=whatsapp).exists():
            messages.error(request, 'Este WhatsApp já está cadastrado!')
            return render(request, 'clients/form.html')
        
        Client.objects.create(
            name=request.POST.get('name'),
            whatsapp=whatsapp,
            city=request.POST.get('city') or None,
            observations=request.POST.get('observations') or None,
        )
        messages.success(request, 'Cliente criado com sucesso!')
        return redirect('clients_list')
    
    return render(request, 'clients/form.html')


@login_required
def client_edit(request, pk):
    client = get_object_or_404(Client, pk=pk)
    
    if request.method == 'POST':
        whatsapp = request.POST.get('whatsapp', '')
        
        if not validate_whatsapp(whatsapp):
            messages.error(request, 'WhatsApp inválido!')
            return render(request, 'clients/form.html', {'client': client})
        
        if Client.objects.filter(whatsapp__icontains=whatsapp).exclude(pk=pk).exists():
            messages.error(request, 'Este WhatsApp já está cadastrado!')
            return render(request, 'clients/form.html', {'client': client})
        
        client.name = request.POST.get('name')
        client.whatsapp = whatsapp
        client.city = request.POST.get('city') or None
        client.observations = request.POST.get('observations') or None
        client.save()
        messages.success(request, 'Cliente atualizado!')
        return redirect('clients_list')
    
    return render(request, 'clients/form.html', {'client': client})


@login_required
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    sales = Sale.objects.filter(client=client).order_by('-created_at')[:20]
    
    total_purchases = sum(float(s.total) for s in sales)
    total_paid = sum(float(s.paid_amount) for s in sales)
    
    return render(request, 'clients/detail.html', {
        'client': client,
        'sales': sales,
        'total_purchases': total_purchases,
        'total_paid': total_paid
    })


@login_required
def client_delete(request, pk):
    client = get_object_or_404(Client, pk=pk)
    client.delete()
    messages.success(request, 'Cliente excluído!')
    return redirect('clients_list')


@login_required
@require_http_methods(["GET"])
def api_clients(request):
    clients = Client.objects.all()
    search = request.GET.get('search', '')
    
    if search:
        clients = clients.filter(name__icontains=search) | clients.filter(whatsapp__icontains=search)
    
    data = [{
        'id': str(c.id),
        'name': c.name,
        'whatsapp': c.whatsapp,
        'city': c.city,
        'total_due': float(c.total_due),
        'last_purchase': c.last_purchase.strftime('%d/%m/%Y') if c.last_purchase else None,
    } for c in clients[:50]]
    
    return JsonResponse(data, safe=False)


@login_required
def sync_debts(request):
    """Sincroniza o total_due dos clientes com as vendas pendentes"""
    clients = Client.objects.all()
    fixed = 0
    
    for client in clients:
        due = sum(
            float(s.total - s.paid_amount) 
            for s in Sale.objects.filter(client=client).exclude(status__in=['paid', 'canceled'])
        )
        if float(client.total_due) != due:
            client.total_due = due
            client.save()
            fixed += 1
    
    return JsonResponse({
        'fixed': fixed,
        'message': f'{fixed} clientes corrigidos!'
    })