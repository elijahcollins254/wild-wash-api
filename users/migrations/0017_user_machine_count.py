from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0016_location_region'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='machine_count',
            field=models.PositiveIntegerField(default=0, help_text="Number of machines available at this washer's location"),
        ),
    ]
