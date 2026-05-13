from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission


class Command(BaseCommand):
    help = 'Cria grupos de usuários e permissões do sistema'

    def handle(self, *args, **options):
        self.stdout.write('Criando grupos...')
        
        groups_data = {
            'admin': {
                'description': 'Acesso total ao sistema',
                'permissions': []
            },
            'gerente': {
                'description': 'Pode gerenciar vendas, clientes e produtos',
                'permissions': [
                    'add_sale', 'change_sale', 'view_sale', 'delete_sale',
                    'add_client', 'change_client', 'view_client', 'delete_client',
                    'add_product', 'change_product', 'view_product', 'delete_product',
                    'view_sale', 'view_client', 'view_product',
                    'add_payment', 'change_payment', 'view_payment', 'delete_payment',
                ]
            },
            'vendedor': {
                'description': 'Pode criar vendas e editar clientes',
                'permissions': [
                    'add_sale', 'view_sale',
                    'add_client', 'change_client', 'view_client',
                    'view_product',
                    'view_payment',
                ]
            },
        }
        
        for group_name, data in groups_data.items():
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                self.stdout.write(f'  Criado grupo: {group_name}')
            else:
                self.stdout.write(f'  Atualizando grupo: {group_name}')
            
            group.permissions.clear()
            
            for perm_codename in data['permissions']:
                try:
                    perm = Permission.objects.get(codename=perm_codename)
                    group.permissions.add(perm)
                except Permission.DoesNotExist:
                    self.stdout.write(f'    Permissão não encontrada: {perm_codename}')
        
        self.stdout.write(self.style.SUCCESS('\nGrupos criados com sucesso!'))
        self.stdout.write('\nGrupos disponíveis:')
        for g in Group.objects.all():
            self.stdout.write(f'  - {g.name} ({g.permissions.count()} permissões)')