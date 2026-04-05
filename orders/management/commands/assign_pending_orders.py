"""
Management command to assign any pending unassigned orders to riders
Run with: python manage.py assign_pending_orders
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from orders.models import Order
from users.models import Location
from notifications.models import Notification

User = get_user_model()

class Command(BaseCommand):
    help = 'Assign pending unassigned orders to available riders'

    def handle(self, *args, **options):
        # DISABLED: Auto-assignment of riders - now manual by admin
        self.stdout.write(self.style.SUCCESS('Auto-assignment disabled - riders must be assigned manually by admin'))
