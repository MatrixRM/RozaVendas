from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .models import Product


@login_required
def products_list(request):
    products = Product.objects.filter(active=True).order_by('name')
    search = request.GET.get('search', '')
    category = request.GET.get('category', '')
    
    if search:
        products = products.filter(name__icontains=search)
    if category:
        products = products.filter(category=category)
    
    categories = Product.CATEGORIES
    low_stock = Product.objects.filter(active=True, stock__lte=5)
    
    return render(request, 'products/list.html', {
        'products': products,
        'categories': categories,
        'low_stock': low_stock,
        'search': search,
        'selected_category': category
    })


@login_required
def product_new(request):
    if request.method == 'POST':
        Product.objects.create(
            name=request.POST.get('name'),
            category=request.POST.get('category'),
            size=request.POST.get('size') or None,
            color=request.POST.get('color') or None,
            cost=request.POST.get('cost') or 0,
            price=request.POST.get('price'),
            stock=request.POST.get('stock') or 0,
            image=request.FILES.get('image'),
        )
        messages.success(request, 'Produto criado com sucesso!')
        return redirect('products_list')
    
    return render(request, 'products/form.html', {'categories': Product.CATEGORIES, 'sizes': Product.SIZES})


@login_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        product.name = request.POST.get('name')
        product.category = request.POST.get('category')
        product.size = request.POST.get('size') or None
        product.color = request.POST.get('color') or None
        product.cost = request.POST.get('cost') or 0
        product.price = request.POST.get('price')
        product.stock = request.POST.get('stock') or 0
        if request.FILES.get('image'):
            product.image = request.FILES.get('image')
        product.save()
        messages.success(request, 'Produto atualizado!')
        return redirect('products_list')
    
    return render(request, 'products/form.html', {
        'product': product,
        'categories': Product.CATEGORIES,
        'sizes': Product.SIZES
    })


@login_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.active = False
    product.save()
    messages.success(request, 'Produto inativado!')
    return redirect('products_list')


@login_required
@require_http_methods(["GET"])
def api_products(request):
    products = Product.objects.filter(active=True)
    search = request.GET.get('search', '')
    
    if search:
        products = products.filter(name__icontains=search)
    
    data = [{
        'id': str(p.id),
        'name': p.name,
        'category': p.get_category_display(),
        'size': p.size,
        'color': p.color,
        'price': float(p.price),
        'cost': float(p.cost),
        'stock': p.stock,
        'image': p.image.url if p.image else None,
    } for p in products[:50]]
    
    return JsonResponse(data, safe=False)