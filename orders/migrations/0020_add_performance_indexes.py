# Generated migration to add database indexes for performance optimization
# These indexes improve filtering speed on commonly searched fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0019_order_new_status_flow'),
    ]

    operations = [
        # Add indexes for filtering/sorting operations
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
                db_index=True,
                default='requested',
                max_length=20,
            ),
        ),
        
        # Add index to code for faster lookups
        migrations.AlterField(
            model_name='order',
            name='code',
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=32,
                unique=True,
            ),
        ),
        
        # Add index to created_at for sorting/date filtering
        migrations.AlterField(
            model_name='order',
            name='created_at',
            field=models.DateTimeField(
                auto_now_add=True,
                db_index=True,
            ),
        ),
        
        # Add index to customer_name for search operations
        migrations.AlterField(
            model_name='order',
            name='customer_name',
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=255,
                null=True,
            ),
        ),
        
        # Add indexes to foreign keys for filter operations
        # rider index
        migrations.AlterField(
            model_name='order',
            name='rider',
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                help_text='[DEPRECATED] Use pickup_rider or delivery_rider instead',
                null=True,
                on_delete=models.SET_NULL,
                related_name='assigned_orders',
                to='auth.user',
            ),
        ),
        
        # service_location index
        migrations.AlterField(
            model_name='order',
            name='service_location',
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                help_text='The location where this order is being processed',
                null=True,
                on_delete=models.SET_NULL,
                related_name='orders',
                to='users.location',
            ),
        ),
        
        # user index
        migrations.AlterField(
            model_name='order',
            name='user',
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name='orders',
                to='auth.user',
            ),
        ),
        
        # Add index to created_by for manual orders
        migrations.AlterField(
            model_name='order',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                help_text='Staff member who created this manual order',
                null=True,
                on_delete=models.SET_NULL,
                related_name='created_orders',
                to='auth.user',
            ),
        ),
        
        # Add indexes to pickup_rider and delivery_rider for filtering
        migrations.AlterField(
            model_name='order',
            name='pickup_rider',
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                help_text='Rider who picks up from customer',
                null=True,
                on_delete=models.SET_NULL,
                related_name='pickup_orders',
                to='auth.user',
            ),
        ),
        
        migrations.AlterField(
            model_name='order',
            name='delivery_rider',
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                help_text='Rider who delivers to customer',
                null=True,
                on_delete=models.SET_NULL,
                related_name='delivery_orders',
                to='auth.user',
            ),
        ),
    ]
