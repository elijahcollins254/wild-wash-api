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
# Use absolute path for production Vercel deployment
BASE_DIR = Path(__file__).resolve().parent.parent
STATICFILES_ROOT = os.path.join(str(BASE_DIR), 'staticfiles')

if os.path.exists(STATICFILES_ROOT):
    app = WhiteNoise(
        app, 
        root=STATICFILES_ROOT,
        max_age=31536000,  # 1 year
        autorefresh=False,
        add_headers_function=None
    )
else:
    # Create a minimal WhiteNoise app even if staticfiles don't exist yet
    app = WhiteNoise(app, root=str(BASE_DIR), autorefresh=True)
