from django.db import migrations, models
import django.db.models.deletion


def link_existing_order_payments(apps, schema_editor):
    Payment = apps.get_model('payments', 'Payment')
    Order = apps.get_model('orders', 'Order')
    orders_by_code = {order.code: order.pk for order in Order.objects.all()}

    for payment in Payment.objects.filter(order__isnull=True).iterator():
        reference = (payment.raw_payload or {}).get('order_reference')
        order_pk = orders_by_code.get(reference)
        if order_pk:
            Payment.objects.filter(pk=payment.pk).update(order_id=order_pk)


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0021_order_pickup_latitude_order_pickup_longitude'),
        ('payments', '0003_tradein'),
    ]

    operations = [
        migrations.RenameField(
            model_name='payment',
            old_name='order_id',
            new_name='legacy_order_id',
        ),
        migrations.AlterField(
            model_name='payment',
            name='legacy_order_id',
            field=models.PositiveIntegerField(blank=True, db_column='order_id', help_text='Legacy numeric order reference', null=True),
        ),
        migrations.AddField(
            model_name='payment',
            name='order',
            field=models.ForeignKey(blank=True, db_column='order_fk_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payments', to='orders.order'),
        ),
        migrations.RunPython(link_existing_order_payments, migrations.RunPython.noop),
    ]