# Generated migration to add database indexes for performance optimization
# These indexes improve filtering speed on commonly searched fields

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0019_order_new_status_flow'),
    ]

    operations = [
        # Create indexes directly via SQL to avoid dependency issues
        # This will create indexes if they don't already exist
        migrations.RunSQL(
            sql=[
                # Index on status for filtering
                'CREATE INDEX IF NOT EXISTS orders_order_status_idx ON orders_order(status);',
                # Index on code for lookups
                'CREATE INDEX IF NOT EXISTS orders_order_code_idx ON orders_order(code);',
                # Index on created_at for sorting
                'CREATE INDEX IF NOT EXISTS orders_order_created_at_idx ON orders_order(created_at);',
                # Index on customer_name for search
                'CREATE INDEX IF NOT EXISTS orders_order_customer_name_idx ON orders_order(customer_name);',
                # Index on rider for filtering
                'CREATE INDEX IF NOT EXISTS orders_order_rider_id_idx ON orders_order(rider_id);',
                # Index on service_location for location filtering
                'CREATE INDEX IF NOT EXISTS orders_order_service_location_id_idx ON orders_order(service_location_id);',
                # Index on user for user filtering
                'CREATE INDEX IF NOT EXISTS orders_order_user_id_idx ON orders_order(user_id);',
                # Index on created_by for manual orders
                'CREATE INDEX IF NOT EXISTS orders_order_created_by_id_idx ON orders_order(created_by_id);',
                # Index on pickup_rider for filtering
                'CREATE INDEX IF NOT EXISTS orders_order_pickup_rider_id_idx ON orders_order(pickup_rider_id);',
                # Index on delivery_rider for filtering
                'CREATE INDEX IF NOT EXISTS orders_order_delivery_rider_id_idx ON orders_order(delivery_rider_id);',
            ],
            reverse_sql=[
                # Drop indexes if rolling back
                'DROP INDEX IF EXISTS orders_order_status_idx;',
                'DROP INDEX IF EXISTS orders_order_code_idx;',
                'DROP INDEX IF EXISTS orders_order_created_at_idx;',
                'DROP INDEX IF EXISTS orders_order_customer_name_idx;',
                'DROP INDEX IF EXISTS orders_order_rider_id_idx;',
                'DROP INDEX IF EXISTS orders_order_service_location_id_idx;',
                'DROP INDEX IF EXISTS orders_order_user_id_idx;',
                'DROP INDEX IF EXISTS orders_order_created_by_id_idx;',
                'DROP INDEX IF EXISTS orders_order_pickup_rider_id_idx;',
                'DROP INDEX IF EXISTS orders_order_delivery_rider_id_idx;',
            ]
        ),
    ]
