from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("services", "0009_service_image_link"),
    ]

    operations = [
        migrations.AlterField(
            model_name="service",
            name="image_link",
            field=models.URLField(
                blank=True,
                help_text=(
                    "Public image URL returned to mobile clients as image_url. "
                    "Known service names are mapped automatically when this is blank."
                ),
                max_length=1000,
                verbose_name="Image URL",
            ),
        ),
    ]
