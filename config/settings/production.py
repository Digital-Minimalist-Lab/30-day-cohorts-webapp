from .base import *

DEBUG = False

# Security settings for production.
# Tell Django to trust the X-Forwarded-Proto header from Railway's proxy.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# Redirect all non-HTTPS requests to HTTPS.
SECURE_SSL_REDIRECT = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'


APP_HOST = os.getenv('RAILWAY_PUBLIC_DOMAIN', 'intentionaltech.ca')

if APP_HOST:
    ALLOWED_HOSTS = [APP_HOST]
    SITE_URL = f'https://{APP_HOST}'
    CSRF_TRUSTED_ORIGINS = [f'https://{APP_HOST}']
