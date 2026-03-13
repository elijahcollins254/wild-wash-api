import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')
django.setup()
from services.models import ServiceCategory
for cat in ServiceCategory.objects.all():
    print(f"ID: {cat.id}, Name: {cat.name}, Slug: {cat.slug}")
