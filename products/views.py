import json
import base64
import io
import csv
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from PIL import Image
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .models import Product, ImportBatch


MONEY = Decimal('0.01')
VALID_CATEGORIES = {choice[0] for choice in Product.CATEGORIES}


def money(value):
    try:
        return Decimal(str(value or 0).replace(',', '.')).quantize(MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0.00')


def positive_int(value, default=0):
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return default


def normalize_category(category):
    aliases = {
        'calcinha': 'lingerie',
        'sutia': 'lingerie',
        'sutiã': 'lingerie',
        'roupas': 'camiseta',
        'pijama': 'lingerie',
        'infantil': 'lingerie',
        'outros': 'lingerie',
        'lençol': 'lingerie',
    }
    category = aliases.get(category, category)
    return category if category in VALID_CATEGORIES else 'lingerie'


def parse_import_csv(uploaded_file):
    raw = uploaded_file.read()
    text = None
    for encoding in ('utf-8-sig', 'utf-8', 'latin-1', 'cp1252'):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        raise ValueError('Não foi possível ler o arquivo CSV.')

    sample = text[:2048]
    delimiter = ';' if ';' in sample else ','
    if delimiter == ',':
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=',|\t').delimiter
        except csv.Error:
            delimiter = ','

    dict_reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    known_headers = {
        'codigo', 'código', 'cod', 'code', 'sku',
        'nome', 'descricao', 'descrição', 'produto', 'description',
        'preco', 'preço', 'valor', 'custo',
    }
    fieldnames = {str(name or '').strip().lower() for name in (dict_reader.fieldnames or [])}
    rows = list(dict_reader) if fieldnames & known_headers else []

    if not rows:
        rows = []
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        for line in reader:
            if len(line) < 3:
                continue
            if str(line[0]).strip().lower() in known_headers:
                continue
            rows.append({
                'codigo': line[0],
                'nome': line[1],
                'preco': line[2],
                'quantidade': line[3] if len(line) > 3 else 1,
            })

    def pick(row, names):
        normalized = {str(k or '').strip().lower(): v for k, v in row.items()}
        for name in names:
            if name in normalized:
                return normalized[name]
        return ''

    products = []
    for row in rows:
        code = str(pick(row, ['codigo', 'código', 'cod', 'code', 'sku'])).strip()
        name = str(pick(row, ['nome', 'descricao', 'descrição', 'produto', 'description'])).strip()
        cost = money(pick(row, ['preco', 'preço', 'valor', 'custo', 'unit', 'unitario', 'unitário']))
        quantity = positive_int(pick(row, ['quantidade', 'qtd', 'qtde', 'qty']), default=1)
        category = normalize_category(pick(row, ['categoria', 'category']) or infer_category(name))

        if not code or not name or cost <= 0 or quantity <= 0:
            continue

        products.append({
            'codigo': code,
            'nome': name.upper(),
            'preco': float(cost),
            'quantidade': quantity,
            'categoria': category,
        })

    return products


@login_required
def products_list(request):
    products = Product.objects.filter(active=True).order_by('name')
    search = request.GET.get('search', '')
    category = request.GET.get('category', '')
    
    if search:
        from django.db.models import Q
        products = products.filter(Q(name__icontains=search) | Q(supplier_code__icontains=search))
    if category:
        products = products.filter(category=category)
    
    categories = Product.CATEGORIES
    from core.models import Settings
    min_stock = int(Settings.get('min_stock', '5'))
    low_stock = Product.objects.filter(active=True, stock__lte=min_stock)
    
    return render(request, 'products/list.html', {
        'products': products,
        'categories': categories,
        'low_stock': low_stock,
        'search': search,
        'selected_category': category
    })


@login_required
def product_new(request):
    from core.models import Settings
    from django.conf import settings
    
    profit_margin = float(Settings.get('profit_margin', settings.PROFIT_MARGIN * 100))
    
    if request.method == 'POST':
        cost = money(request.POST.get('cost'))
        price = money(request.POST.get('price'))
        stock = positive_int(request.POST.get('stock'))
        
        if price == 0 and cost > 0:
            price = money(cost * (Decimal(str(Settings.get('profit_margin', settings.PROFIT_MARGIN * 100))) / Decimal('100') + Decimal('1')))

        if not request.POST.get('name'):
            messages.error(request, 'Informe o nome do produto.')
            return redirect('product_new')

        if price <= 0:
            messages.error(request, 'Informe um preço de venda maior que zero.')
            return redirect('product_new')
        
        Product.objects.create(
            name=request.POST.get('name'),
            supplier_code=request.POST.get('supplier_code') or None,
            category=normalize_category(request.POST.get('category')),
            size=request.POST.get('size') or None,
            color=request.POST.get('color') or None,
            cost=cost,
            price=price,
            stock=stock,
            image=request.FILES.get('image'),
        )
        messages.success(request, 'Produto criado com sucesso!')
        return redirect('products_list')
    
    return render(request, 'products/form.html', {
        'categories': Product.CATEGORIES,
        'sizes': Product.SIZES,
        'profit_margin': profit_margin
    })


@login_required
def product_edit(request, pk):
    from core.models import Settings
    from django.conf import settings
    
    product = get_object_or_404(Product, pk=pk)
    profit_margin = float(Settings.get('profit_margin', settings.PROFIT_MARGIN * 100))
    
    if request.method == 'POST':
        cost = money(request.POST.get('cost'))
        price = money(request.POST.get('price'))
        stock = positive_int(request.POST.get('stock'))
        
        if price == 0 and cost > 0:
            price = money(cost * (Decimal(str(Settings.get('profit_margin', settings.PROFIT_MARGIN * 100))) / Decimal('100') + Decimal('1')))

        if not request.POST.get('name'):
            messages.error(request, 'Informe o nome do produto.')
            return redirect('product_edit', pk=pk)

        if price <= 0:
            messages.error(request, 'Informe um preço de venda maior que zero.')
            return redirect('product_edit', pk=pk)
        
        product.name = request.POST.get('name')
        product.supplier_code = request.POST.get('supplier_code') or None
        product.category = normalize_category(request.POST.get('category'))
        product.size = request.POST.get('size') or None
        product.color = request.POST.get('color') or None
        product.cost = cost
        product.price = price
        product.stock = stock
        if request.FILES.get('image'):
            product.image = request.FILES.get('image')
        product.save()
        messages.success(request, 'Produto atualizado!')
        return redirect('products_list')
    
    return render(request, 'products/form.html', {
        'product': product,
        'categories': Product.CATEGORIES,
        'sizes': Product.SIZES,
        'profit_margin': profit_margin
    })


@login_required
@require_http_methods(["POST"])
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
        'code': p.supplier_code,
        'category': p.get_category_display(),
        'size': p.size,
        'color': p.color,
        'price': float(p.price),
        'cost': float(p.cost),
        'stock': p.stock,
        'image': p.image.url if p.image else None,
    } for p in products[:50]]
    
    return JsonResponse(data, safe=False)


CATEGORY_KEYWORDS = {
    'lingerie': ['tanga', 'sutien', 'sutiã', 'fio dental', 'calcinha', 'biquíni', 'bikini', 'lingerie', ' bodies', 'corselet', 'conjunto'],
    'cueca': ['cueca', 'box', 'sunga', 'calcador'],
    'meia': ['meia', 'meias', 'sock'],
    'moletom': ['moletom', 'moletin', 'blusão', 'blusao', 'jogger', 'bermuda moletom'],
    'camiseta': ['camiseta', 'camiseta', 'blusa', 'regata', 'polo'],
    'legging': ['legging', 'calça legging', 'calça'],
    'pijama': ['pijama', 'pijamas', 'camisola'],
    'lençol': ['lençol', 'lencol', 'edredom', 'coberta', 'toalha'],
}


def infer_category(product_name):
    name_lower = product_name.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in name_lower:
                return category
    return 'lingerie'


def calculate_selling_price(cost_price):
    """Calcula preço de venda com base no custo + margem"""
    from django.conf import settings
    from core.models import Settings
    
    margin = Decimal(str(Settings.get('profit_margin', settings.PROFIT_MARGIN * 100))) / Decimal('100')
    return money(money(cost_price) * (Decimal('1') + margin))


def parse_product_list(text):
    import re
    products = []
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 3:
            continue
        
        # Ignorar linhas que parecem ser cabeçalhos ou rodapés
        lower = line.lower()
        if any(skip in lower for skip in ['spc', 'continua', 'total', 'page', 'página', 'fornecedor', 'lista', 'data', 'não', 'consegui', 'identificar', 'ajudar']):
            continue
        
        # Padrão: CODIGO | NOME | PRECO | QTD
        # ou: CODIGO NOME PRECO QTD
        patterns = [
            r'(\d+)\s*[\|\-]\s*([A-Za-zÀ-ÖØ-öø-ÿ\s]+?)\s*[\|\-]\s*([\d.,]+)\s*[\|\-]\s*(\d+)',
            r'(\d+)\s+([A-Za-zÀ-ÖØ-öø-ÿ\s]+?)\s+([\d.,]+)\s+(\d+)',
            r'(\d+)\s+([A-Za-zÀ-ÖØ-öø-ÿ\s]+?)\s+R?\$?\s*([\d.,]+)',
        ]
        
        matched = False
        for pattern in patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                groups = match.groups()
                code = groups[0]
                name = groups[1].strip()
                price = float(groups[2].replace(',', '.'))
                qty = int(groups[3]) if len(groups) > 3 and groups[3].isdigit() else 1
                
                if price > 0 and name and len(name) > 1:
                    products.append({
                        'codigo': code,
                        'nome': name.upper(),
                        'preco': price,
                        'quantidade': qty,
                        'categoria': infer_category(name)
                    })
                    matched = True
                    break
        
        # Se ainda não encontrou, tentar extrair código no início seguido de texto e número
        if not matched:
            simple_match = re.match(r'^(\d+)\s+(.+)$', line)
            if simple_match:
                code = simple_match.group(1)
                rest = simple_match.group(2)
                
                # Procurar preço e quantidade no resto
                price_match = re.search(r'([\d.,]+)', rest)
                qty_match = re.search(r'\s+(\d+)\s*$', rest)
                
                if price_match:
                    price = float(price_match.group(1).replace(',', '.'))
                    name = re.sub(r'[\d.,]+', '', rest).strip()
                    qty = int(qty_match.group(1)) if qty_match else 1
                    
                    if price > 0 and name:
                        products.append({
                            'codigo': code,
                            'nome': name.upper(),
                            'preco': price,
                            'quantidade': qty,
                            'categoria': infer_category(name)
                        })
    
    return products


@login_required
def product_import(request):
    if request.method == 'POST':
        import_file = request.FILES.get('import_file') or request.FILES.get('image')
        image = import_file
        
        if not import_file:
            messages.error(request, 'Selecione um arquivo CSV ou uma imagem')
            return redirect('product_import')

        filename = (import_file.name or '').lower()
        if filename.endswith('.csv') or import_file.content_type in ['text/csv', 'application/vnd.ms-excel']:
            try:
                products = parse_import_csv(import_file)
            except ValueError as exc:
                messages.error(request, str(exc))
                return redirect('product_import')

            if not products:
                messages.error(request, 'Nenhum produto válido encontrado no CSV.')
                return redirect('product_import')

            total_value = sum(p['preco'] * p.get('quantidade', 1) for p in products)
            batch = ImportBatch.objects.create(
                total_products=len(products),
                total_value=total_value,
                raw_ocr_text=f'CSV importado: {import_file.name}',
                created_by=request.user
            )

            return render(request, 'products/import.html', {
                'step': 'preview',
                'products': products,
                'products_json': json.dumps(products),
                'total_value': total_value,
                'batch_id': str(batch.id),
                'warning': None
            })
        
        # Ler imagem e converter para base64
        from PIL import Image
        import io
        
        img = Image.open(image)
        
        # Redimensionar se muito grande (max 1024px)
        max_size = 1024
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        # Converter para JPEG com qualidade reduzida
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        # Usar ChatService para processar a imagem
        from chat.service import get_chat_service
        from chat.models import AISettings
        
        chat_service = get_chat_service()
        
        # Debug: verificar configuração
        from chat.models import AISettings
        active = AISettings.get_active()
        if active:
            print(f"DEBUG - Model no DB: {active.model}")
            print(f"DEBUG - Provider no DB: {active.provider}")
        
        if not chat_service:
            ai_active = AISettings.get_active()
            if not ai_active:
                messages.error(request, '⚠️ Chat IA não está configurado. Configure em Chat > Configurações primeiro.')
            else:
                messages.error(request, '⚠️ Chat IA não está ativo. Ative em Chat > Configurações.')
            return redirect('product_import')
        
        prompt = """PROCESSE ESTA TABELA COMPLETAMENTE

Esta imagem tem uma tabela de produtos. Sua tarefa é EXTRAIR TODAS as linhas.

IMPORTANTE:
1. Conte as linhas da tabela (ignore cabeçalhos)
2. Liste CADA produto: codigo,nome,preco,quantidade
3. USE virgula como separador de campos
4. NÃO invente, NÃO pule, NÃO altere

Exemplo de saída EXATA que eu quero:
107,TANGA SIMPLES,26.90,6
108,CALCINHA FIO DENTAL,31.90,5
109,SUTIA BASICO,35.00,3
110,CUECA ADULTO,44.90,4
...

Não importa o tamanho da lista - Liste TODOS os produtos visíveis.

IMPORTANTE: No inicio da resposta, escreva:
TOTAL_LINHAS: [numero]

Exemplo:
TOTAL_LINHAS: 35
107,TANGA SIMPLES,26.90,6
108,CALCINHA FIO DENTAL,31.90,5
...

Retorne APENAS texto puro, sem markdown, sem explicações."""

        messages_data = [
            {"role": "system", "content": "Você é um extrator inteligente de produtos de listas impressas."},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
                {"type": "text", "text": prompt}
            ]}
        ]
        
        try:
            import requests
            # Debug: verificar URL
            print(f"DEBUG - API URL: {chat_service.api_url}")
            print(f"DEBUG - Model: {chat_service.model}")
            print(f"DEBUG - Provider: {chat_service.provider}")
            
            headers = {
                "Authorization": f"Bearer {chat_service.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": chat_service.model,
                "messages": messages_data,
                "max_tokens": 6000
            }
            
            response = requests.post(chat_service.api_url, headers=headers, json=data, timeout=60)
            
            if response.status_code != 200:
                messages.error(request, f"Erro {response.status_code}: {response.text[:200]}")
                return redirect('product_import')
            
            if response.status_code == 200:
                result = response.json()
                extracted_text = result['choices'][0]['message']['content']
                
                # Parse do resultado (JSON ou CSV)
                products = []
                total_detected = 0
                
                # Verificar se tem TOTAL_LINHAS no inicio
                lines_text = extracted_text.strip().split('\n')
                for line in lines_text:
                    if 'TOTAL_LINHAS' in line.upper():
                        try:
                            total_detected = int(''.join(filter(str.isdigit, line)))
                        except:
                            pass
                
                # Tentar JSON primeiro
                try:
                    json_start = extracted_text.find('{')
                    json_end = extracted_text.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_text = extracted_text[json_start:json_end]
                        data = json.loads(json_text)
                        products = data.get('produtos', [])
                except:
                    pass
                
                # Se não achou JSON, tentar CSV
                if not products:
                    for line in extracted_text.strip().split('\n'):
                        line = line.strip()
                        # Pular linha de TOTAL
                        if 'TOTAL_LINHAS' in line.upper():
                            continue
                        if not line or ',' not in line:
                            continue
                        line = line.strip()
                        if not line or ',' not in line:
                            continue
                        # Pular linhas que não são dados
                        if line.lower().startswith('codigo') or line.lower().startswith('produto'):
                            continue
                        
                        parts = line.split(',')
                        if len(parts) >= 2:
                            try:
                                code = parts[0].strip()
                                name = parts[1].strip()
                                price = float(parts[2].strip().replace(',', '.')) if len(parts) > 2 and parts[2].strip() else 0
                                qty = int(parts[3].strip()) if len(parts) > 3 and parts[3].strip() else 1
                                
                                if code and name and price > 0:
                                    products.append({
                                        'codigo': code,
                                        'nome': name,
                                        'preco': price,
                                        'quantidade': qty
                                    })
                            except:
                                continue
                
                if not products:
                    messages.error(request, '⚠️ A IA não conseguiu identificar produtos na imagem. Tente uma foto mais clara.')
                    return redirect('product_import')
                
                # Alerta se detectou menos linhas
                warning = None
                if total_detected > 0 and len(products) < total_detected:
                    warning = f"Atenção: A IA reportou {total_detected} linhas, mas só conseguiu extrair {len(products)}. possibly há produtos faltando."
                elif len(products) < 20:
                    warning = f"Poucos produtos ({len(products)}) detectados. Verifique se a foto está clara."
                
                # Corrigir categorias baseado no nome do produto (não confiar na IA)
                def fix_category(product):
                    name = product.get('nome', '').upper()
                    
                    # Palavras-chave por categoria
                    keywords = {
                        'lingerie': ['TANGA', 'CALCINHA', 'FIO DENTAL', 'TANGUE', 'CARDIGUE', 'SUTIA', 'SUTIAN', 'BRA', 'TOP', 'BUSTIE', 'SOUTIEN', 'PIJAMA', 'CAMISOLA'],
                        'cueca': ['CUECA', 'CALCAO', 'SLIP', 'BOXER'],
                        'meia': ['MEIA', 'MEIAS'],
                        'moletom': ['MOLETOM', 'MOLETIN', 'JOGGER'],
                        'legging': ['CALCA', 'LEGGING'],
                        'camiseta': ['BERMUDA', 'SHORT', 'SAIA', 'JEANS', 'VESTIDO', 'BLUSA', 'CAMISETA', 'REGATA'],
                    }
                    
                    for cat, kws in keywords.items():
                        for kw in kws:
                            if kw in name:
                                return cat
                    
                    return normalize_category(product.get('categoria', 'lingerie'))
                
                for p in products:
                    p['categoria'] = fix_category(p)
                
                # Criar batch
                batch = ImportBatch.objects.create(
                    total_products=len(products),
                    total_value=sum(p['preco'] * p.get('quantidade', 1) for p in products),
                    raw_ocr_text=extracted_text[:2000],
                    original_image=image,
                    created_by=request.user
                )
                
                # Alertar se poucos produtos
                if not warning and len(products) < 25:
                    warning = f"Atencao: Apenas {len(products)} produtos detectados. Se a lista tem mais produtos, tire uma foto mais clara."
                
                # Renderizar preview
                return render(request, 'products/import.html', {
                    'step': 'preview',
                    'products': products,
                    'products_json': json.dumps(products),
                    'total_value': sum(p['preco'] * p.get('quantidade', 1) for p in products),
                    'batch_id': str(batch.id),
                    'warning': warning
                })
            else:
                messages.error(request, f'Erro ao processar imagem: {response.status_code}')
                return redirect('product_import')
                
        except Exception as e:
            messages.error(request, f'Erro: {str(e)}')
            return redirect('product_import')
    
    return render(request, 'products/import.html', {'step': 'upload'})


@login_required
def product_import_confirm(request):
    if request.method == 'POST':
        products_data = request.POST.get('products_data', '[]')
        batch_id = request.POST.get('batch_id', '')
        
        try:
            products = json.loads(products_data)
        except:
            messages.error(request, 'Dados inválidos')
            return redirect('product_import')
        
        if not products:
            messages.error(request, 'Nenhum produto para cadastrar')
            return redirect('product_import')
        
        batch = None
        if batch_id:
            batch = ImportBatch.objects.filter(id=batch_id).first()
        
        created_count = 0
        updated_count = 0
        total_value = 0
        
        for p in products:
            cost_price = money(p.get('preco', 0))
            quantity = positive_int(p.get('quantidade', 1), default=1)
            category = normalize_category(p.get('categoria', 'lingerie'))

            if cost_price <= 0 or quantity <= 0:
                continue
            selling_price = calculate_selling_price(cost_price)
            
            # Verificar se produto com mesmo código já existe
            existing = Product.objects.filter(supplier_code=p.get('codigo')).first()
            
            if existing:
                existing.stock += quantity
                existing.cost = cost_price
                existing.price = selling_price
                existing.category = category
                existing.save()
                updated_count += 1
            else:
                product = Product.objects.create(
                    name=p.get('nome', 'Produto'),
                    category=category,
                    cost=cost_price,
                    price=selling_price,
                    stock=quantity,
                    supplier_code=p.get('codigo'),
                    original_name=p.get('nome'),
                    ai_imported=True,
                    import_batch=batch,
                    active=True
                )
                created_count += 1
            
            total_value += cost_price * quantity
        
        messages.success(request, f'{created_count} produtos criados, {updated_count} atualizados!')
        
        return render(request, 'products/import.html', {
            'step': 'success',
            'count': created_count + updated_count,
            'total_value': total_value
        })
    
    return redirect('product_import')
