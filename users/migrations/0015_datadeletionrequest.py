from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0014_user_pickup_coordinates'),
    ]

    operations = [
        migrations.CreateModel(
            name='DataDeletionRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('request_type', models.CharField(choices=[('account', 'Account and associated data'), ('data', 'Selected personal data')], max_length=20)),
                ('details', models.TextField(blank=True)),
                ('account_email', models.EmailField(blank=True, max_length=254)),
                ('account_phone', models.CharField(blank=True, max_length=32)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('in_progress', 'In progress'), ('completed', 'Completed'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                ('review_notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='data_deletion_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]