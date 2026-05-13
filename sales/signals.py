from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from sales.models import Sale


@receiver(post_save, sender=Sale)
def update_client_total_due(sender, instance, **kwargs):
    if instance.client:
        instance.client.sync_total_due()


@receiver(post_delete, sender=Sale)
def delete_client_total_due(sender, instance, **kwargs):
    if instance.client:
        instance.client.sync_total_due()