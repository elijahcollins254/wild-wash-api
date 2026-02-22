"""
WSGI config for api project.

It exposes the WSGI callable as a module-level variable named ``app``.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/howto/deployment/wsgi/
"""

import os
from pathlib import Path

from django.core.wsgi import get_wsgi_application
from whitenoise import WhiteNoise

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')

app = get_wsgi_application()

# Serve static files with WhiteNoise
# WhiteNoise handles MIME types, caching, and compression automatically
BASE_DIR = Path(__file__).resolve().parent.parent
STATICFILES_ROOT = os.path.join(str(BASE_DIR), 'staticfiles')

app = WhiteNoise(
    app,
    root=STATICFILES_ROOT if os.path.exists(STATICFILES_ROOT) else str(BASE_DIR),
    max_age=31536000,  # 1 year cache for versioned files
    autorefresh=False,
    index_file=True,  # Serve index.html for directory requests
    follow_symlinks=True
)
