from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('offers', '0003_offer_image_url'),
    ]

    operations = [
        migrations.CreateModel(
            name='Banner',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('image_url', models.URLField(help_text='Public image URL for this homepage carousel banner.', max_length=1000, verbose_name='Image URL')),
                ('button_text', models.CharField(blank=True, help_text='Text shown on the banner button, for example: Explore services.', max_length=50)),
                ('link_url', models.URLField(help_text='Where the banner button or image should open.', max_length=1000)),
                ('is_active', models.BooleanField(default=True)),
                ('valid_from', models.DateTimeField(default=django.utils.timezone.now)),
                ('valid_until', models.DateTimeField(blank=True, null=True)),
                ('sort_order', models.PositiveIntegerField(default=0, help_text='Lower numbers appear first.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ('sort_order', '-created_at'),
            },
        ),
    ]
