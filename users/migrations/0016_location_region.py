from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0015_datadeletionrequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='location',
            name='region',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]