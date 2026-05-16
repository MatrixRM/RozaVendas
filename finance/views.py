from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from django.http import HttpResponse
from clients.models import Client
from sales.models import Sale
from core.models import Settings
from django.conf import settings
from fpdf import FPDF
from datetime import datetime
import os


@login_required
def dashboard(request):
    now = timezone.now()
    today = now.date()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_sales = Sale.objects.exclude(status='canceled').filter(created_at__gte=month_start)
    
    today_sales = Sale.objects.exclude(status='canceled').filter(created_at__gte=today_start)
    
    total_today = today_sales.aggregate(Sum('total'))['total__sum'] or 0
    total_month = month_sales.aggregate(Sum('total'))['total__sum'] or 0
    commission_rate = float(Settings.get('commission_rate', settings.COMISSION_RATE * 100)) / 100
    commission_month = float(total_month) * commission_rate
    profit_month = month_sales.aggregate(Sum('profit'))['profit__sum'] or 0
    
    debtors = Client.objects.filter(total_due__gt=0).order_by('-total_due')
    total_debt = sum(float(c.total_due) for c in debtors)
    
    pending_sales = Sale.objects.exclude(status='canceled').filter(status__in=['pending', 'partial', 'overdue'])
    pending_amount = sum(float(s.total - s.paid_amount) for s in pending_sales)
    
    recent_sales = Sale.objects.exclude(status='canceled')[:10]
    
    return render(request, 'finance/dashboard.html', {
        'total_today': total_today,
        'total_month': total_month,
        'commission_month': commission_month,
        'profit_month': profit_month,
        'debtors': debtors,
        'total_debt': total_debt,
        'pending_amount': pending_amount,
        'pending_count': pending_sales.count(),
        'recent_sales': recent_sales,
    })


@login_required
def debtors_list(request):
    debtors = Client.objects.filter(total_due__gt=0).order_by('-total_due')
    total = sum(float(c.total_due) for c in debtors)
    
    return render(request, 'finance/debtors.html', {
        'debtors': debtors,
        'total': total,
    })


@login_required
def reports(request):
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    
    month_sales = Sale.objects.exclude(status='canceled').filter(created_at__gte=month_start)
    year_sales = Sale.objects.exclude(status='canceled').filter(created_at__gte=year_start)
    
    commission_rate = float(Settings.get('commission_rate', settings.COMISSION_RATE * 100)) / 100
    
    month_total = float(month_sales.aggregate(Sum('total'))['total__sum'] or 0)
    month_profit = float(month_sales.aggregate(Sum('profit'))['profit__sum'] or 0)
    month_count = month_sales.count()
    year_total = float(year_sales.aggregate(Sum('total'))['total__sum'] or 0)
    year_profit = float(year_sales.aggregate(Sum('profit'))['profit__sum'] or 0)
    year_count = year_sales.count()
    
    data = {
        'month': {
            'sales': month_total,
            'commission': float(month_sales.aggregate(Sum('commission'))['commission__sum'] or 0),
            'profit': month_profit,
            'count': month_count,
            'average': month_total / month_count if month_count > 0 else 0,
        },
        'year': {
            'sales': year_total,
            'commission': float(year_sales.aggregate(Sum('commission'))['commission__sum'] or 0),
            'profit': year_profit,
            'count': year_count,
            'average': year_total / year_count if year_count > 0 else 0,
        },
    }
    
    return render(request, 'finance/reports.html', data)


def remove_accents(text):
    import unicodedata
    if not text:
        return ''
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


class PDFReport(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 14)
        self.cell(0, 10, 'Roza Vendas - Relatorio de Vendas', align='C', new_x='LMARGIN', new_y='NEXT')
        self.set_font('helvetica', '', 10)
        self.cell(0, 8, f'Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M")}', align='C', new_x='LMARGIN', new_y='NEXT')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}', align='C')


@login_required
def sales_pdf(request):
    period = request.GET.get('period', 'month')
    now = timezone.now()
    
    if period == 'today':
        sales = Sale.objects.exclude(status='canceled').filter(created_at__date=now.date())
        period_name = 'Hoje'
    elif period == 'year':
        year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        sales = Sale.objects.exclude(status='canceled').filter(created_at__gte=year_start)
        period_name = f'Ano ({now.year})'
    else:
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        sales = Sale.objects.exclude(status='canceled').filter(created_at__gte=month_start)
        period_name = f'Mes {now.strftime("%m/%Y")}'
    
    if not sales.exists():
        return HttpResponse('Nenhuma venda neste periodo', status=404)
    
    pdf = PDFReport()
    pdf.add_page()
    
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(0, 10, f'Periodo: {period_name}', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(5)
    
    total_vendas = 0
    total_lucro = 0
    total_comissao = 0
    
    products_summary = {}
    
    for sale in sales.order_by('-created_at'):
        total_vendas += float(sale.total)
        total_lucro += float(sale.profit or 0)
        total_comissao += float(sale.commission or 0)
        
        pdf.set_font('helvetica', '', 9)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(0, 8, f'Venda #{sale.id} - {sale.created_at.strftime("%d/%m/%Y %H:%M")} - Cliente: {sale.client.name if sale.client else "Consumidor"}', fill=True, new_x='LMARGIN', new_y='NEXT')
        
        pdf.set_font('helvetica', '', 8)
        pdf.cell(15, 7, 'Qtd')
        pdf.cell(60, 7, 'Produto')
        pdf.cell(30, 7, 'Preco Unit.')
        pdf.cell(30, 7, 'Subtotal', new_x='LMARGIN', new_y='NEXT')
        
        for product in sale.products:
            qty = product.get('quantity', 1)
            name = product.get('name', 'Produto')[:30]
            price = float(product.get('price', 0))
            subtotal = price * qty
            
            pdf.cell(15, 6, str(qty))
            pdf.cell(60, 6, name)
            pdf.cell(30, 6, f'R$ {price:.2f}')
            pdf.cell(30, 6, f'R$ {subtotal:.2f}', new_x='LMARGIN', new_y='NEXT')
            
            if name in products_summary:
                products_summary[name]['quantity'] += qty
                products_summary[name]['total'] += subtotal
            else:
                products_summary[name] = {'quantity': qty, 'total': subtotal}
        
        pdf.set_font('helvetica', 'B', 9)
        pdf.cell(105, 7, 'Total venda:')
        pdf.cell(30, 7, f'R$ {float(sale.total):.2f}', new_x='LMARGIN', new_y='NEXT')
        pdf.ln(3)
    
    pdf.ln(10)
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(0, 10, 'RESUMO DO PERIODO', new_x='LMARGIN', new_y='NEXT')
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(0, 8, f'Total de vendas: {sales.count()}', fill=True, new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 8, f'Total vendido: R$ {total_vendas:.2f}', fill=True, new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 8, f'Comissao: R$ {total_comissao:.2f}', fill=True, new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 8, f'Lucro liquido: R$ {total_lucro:.2f}', fill=True, new_x='LMARGIN', new_y='NEXT')
    
    pdf.ln(10)
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(0, 10, 'PRODUTOS VENDIDOS', new_x='LMARGIN', new_y='NEXT')
    
    sorted_products = sorted(products_summary.items(), key=lambda x: x[1]['total'], reverse=True)
    
    pdf.set_font('helvetica', '', 9)
    pdf.cell(80, 8, 'Produto')
    pdf.cell(30, 8, 'Qtd Total')
    pdf.cell(40, 8, 'Total', new_x='LMARGIN', new_y='NEXT')
    
    for name, data in sorted_products:
        pdf.cell(80, 6, name[:40])
        pdf.cell(30, 6, str(data['quantity']))
        pdf.cell(40, 6, f'R$ {data["total"]:.2f}', new_x='LMARGIN', new_y='NEXT')
    
    pdf_data = bytes(pdf.output())
    response = HttpResponse(pdf_data, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="relatorio_vendas_{period}_{now.strftime("%Y%m%d")}.pdf"'
    return response