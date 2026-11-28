from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0023_orderreview_delete_orderrating'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='order_type',
            field=models.CharField(
                choices=[
                    ('online', 'Online Order'),
                    ('manual', 'Staff-Created Order'),
                    ('partner', 'Partner-Created Order'),
                ],
                default='online',
                help_text='How the order was created: online, staff-created, or partner-created',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='partner_paid_sms_sent_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the partner-order payment and rating SMS was sent',
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name='orderreview',
            name='customer',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='order_reviews',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
