# Generated migration for new order status flow and rider tracking

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('orders', '0018_order_payment_method'),
    ]

    operations = [
        # Add new status choices
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(
                choices=[
                    ('requested', 'Order Requested'),
                    ('pending_assignment', 'Pending Pickup Assignment'),
                    ('assigned_pickup', 'Assigned for Pickup'),
                    ('picked', 'Picked Up'),
                    ('in_progress', 'In Progress'),
                    ('washed', 'Washed'),
                    ('folded', 'Folded'),
                    ('ready', 'Ready for Delivery'),
                    ('pending_delivery', 'Pending Delivery Assignment'),
                    ('assigned_delivery', 'Assigned for Delivery'),
                    ('delivered', 'Delivered'),
                    ('cancelled', 'Cancelled'),
                ],
                default='requested',
                max_length=20,
            ),
        ),
        
        # Add new rider fields for separate pickup and delivery tracking
        migrations.AddField(
            model_name='order',
            name='pickup_rider',
            field=models.ForeignKey(
                blank=True,
                help_text='Rider who picks up from customer',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='pickup_orders',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='delivery_rider',
            field=models.ForeignKey(
                blank=True,
                help_text='Rider who delivers to customer',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='delivery_orders',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        
        # Add new timestamp fields
        migrations.AddField(
            model_name='order',
            name='picked_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Timestamp when order was picked up',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='ready_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Timestamp when order was ready for delivery',
                null=True,
            ),
        ),
        
        # Update rider field help text to mark as deprecated
        migrations.AlterField(
            model_name='order',
            name='rider',
            field=models.ForeignKey(
                blank=True,
                help_text='[DEPRECATED] Use pickup_rider or delivery_rider instead',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='assigned_orders',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
