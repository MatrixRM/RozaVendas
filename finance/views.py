from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from clients.models import Client
from sales.models import Sale
from core.models import Settings
from django.conf import settings


@login_required
def dashboard(request):
    now = timezone.now()
    today = now.date()
    
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_sales = Sale.objects.exclude(status='canceled').filter(created_at__gte=month_start)
    
    today_sales = Sale.objects.exclude(status='canceled').filter(created_at__date=today)
    
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