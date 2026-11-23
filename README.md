[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fvercel%2Fexamples%2Ftree%2Fmain%2Fpython%2Fdjango&demo-title=Django%20%2B%20Vercel&demo-description=Use%20Django%204%20on%20Vercel%20with%20Serverless%20Functions%20using%20the%20Python%20Runtime.&demo-url=https%3A%2F%2Fdjango-template.vercel.app%2F&demo-image=https://assets.vercel.com/image/upload/v1669994241/random/django.png)

# Django + Vercel

This example shows how to use Django 4 on Vercel with Serverless Functions using the [Python Runtime](https://vercel.com/docs/concepts/functions/serverless-functions/runtimes/python).

## Demo

https://django-template.vercel.app/

## How it Works

Our Django application, `example` is configured as an installed application in `api/settings.py`:

```python
# api/settings.py
INSTALLED_APPS = [
    # ...
    'example',
]
```

We allow "\*.vercel.app" subdomains in `ALLOWED_HOSTS`, in addition to 127.0.0.1:

```python
# api/settings.py
ALLOWED_HOSTS = ['127.0.0.1', '.vercel.app']
```

The `wsgi` module must use a public variable named `app` to expose the WSGI application:

```python
# api/wsgi.py
app = get_wsgi_application()
```

The corresponding `WSGI_APPLICATION` setting is configured to use the `app` variable from the `api.wsgi` module:

```python
# api/settings.py
WSGI_APPLICATION = 'api.wsgi.app'
```

There is a single view which renders the current time in `example/views.py`:

```python
# example/views.py
from datetime import datetime

from django.http import HttpResponse


def index(request):
    now = datetime.now()
    html = f'''
    <html>
        <body>
            <h1>Hello from Vercel!</h1>
            <p>The current time is { now }.</p>
        </body>
    </html>
    '''
    return HttpResponse(html)
```

This view is exposed a URL through `example/urls.py`:

```python
# example/urls.py
from django.urls import path

from example.views import index


urlpatterns = [
    path('', index),
]
```

Finally, it's made accessible to the Django server inside `api/urls.py`:

```python
# api/urls.py
from django.urls import path, include

urlpatterns = [
    ...
    path('', include('example.urls')),
]
```

This example uses the Web Server Gateway Interface (WSGI) with Django to enable handling requests on Vercel with Serverless Functions.

## Running Locally

```bash
python manage.py runserver
```

Your Django application is now available at `http://localhost:8000`.

## Live support chat

The support chat sends customer messages with the existing HTTP API and streams
support replies over Server-Sent Events. The API is served by Daphne through the
repository `Procfile`. Configure `CHANNEL_REDIS_URL` with a shared Redis
connection in deployed environments so replies reach chat connections across
web processes and instances. Without it, Django uses an in-memory channel layer,
which is suitable only for local, single-process development.

## Unique user phone numbers

Before deploying the migration that makes user phone numbers unique, run
`python manage.py audit_duplicate_phones` and save the report so you can
reassign numbers afterward, and retain a database backup. The migration clears
the phone number from every account in each duplicate group, then enforces
uniqueness. This data cleanup cannot be reversed by rolling back migrations. It
does not merge or delete accounts; users without a phone number can keep `phone`
empty. Re-add each number manually only to the account you have verified should
own it.

## One-Click Deploy

Deploy the example using [Vercel](https://vercel.com?utm_source=github&utm_medium=readme&utm_campaign=vercel-examples):

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fvercel%2Fexamples%2Ftree%2Fmain%2Fpython%2Fdjango&demo-title=Django%20%2B%20Vercel&demo-description=Use%20Django%204%20on%20Vercel%20with%20Serverless%20Functions%20using%20the%20Python%20Runtime.&demo-url=https%3A%2F%2Fdjango-template.vercel.app%2F&demo-image=https://assets.vercel.com/image/upload/v1669994241/random/django.png)
