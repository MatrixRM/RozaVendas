from functools import wraps
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required


def role_required(*roles):
    """Decorator que verifica se o usuário tem pelo menos uma das roles"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            user = request.user
            
            if user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            if not user.groups.exists() and not hasattr(user, 'role'):
                return HttpResponseForbidden("Acesso restrito. Contacte o administrador.")
            
            user_roles = list(user.groups.values_list('name', flat=True))
            
            if hasattr(user, 'role'):
                user_roles.append(user.role)
            
            for role in roles:
                if role in user_roles:
                    return view_func(request, *args, **kwargs)
            
            return HttpResponseForbidden("Você não tem permissão para acessar esta função.")
        
        return wrapper
    return decorator


def admin_required(view_func):
    """Decorator para funções que só admins podem acessar"""
    return role_required('admin', 'gerente')(view_func)


def can_sell(view_func):
    """Decorator para funções de venda"""
    return role_required('admin', 'gerente', 'vendedor')(view_func)


def can_view_only(view_func):
    """Decorator para visualização apenas"""
    return role_required('admin', 'gerente', 'vendedor')(view_func)