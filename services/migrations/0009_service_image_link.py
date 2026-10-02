from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0008_alter_service_options_service_category_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='image_link',
            field=models.URLField(
                blank=True,
                help_text='External image URL. When provided, this is used instead of the uploaded image.',
                max_length=1000,
                verbose_name='Image URL',
            ),
        ),
    ]