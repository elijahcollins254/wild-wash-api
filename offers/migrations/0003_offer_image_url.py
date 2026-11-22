from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('offers', '0002_offernotificationsubscription'),
    ]

    operations = [
        migrations.AddField(
            model_name='offer',
            name='image_url',
            field=models.URLField(
                blank=True,
                help_text='Public image URL for this offer.',
                max_length=1000,
                verbose_name='Image URL',
            ),
        ),
    ]
