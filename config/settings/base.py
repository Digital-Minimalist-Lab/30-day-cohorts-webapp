"""
Django settings for digital minimalist cohorts project.
"""
import os
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv
import dj_database_url

# Load environment variables
load_dotenv()

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-me-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True') == 'True'

LANDING_ONLY = os.getenv('LANDING_ONLY', 'False') == 'True'

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    "django.contrib.humanize",

    # Third-party apps
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'django_q',  # Task queue
    'django_q2_email_backend',  # Email backend for Django Q

    # Local apps
    'config',  # For management commands
    'core',
    'accounts',
    'cohorts',
    'surveys',
    'payments',
    'health_check',
]

if LANDING_ONLY:
    # In landing-only mode, we only need these two apps.
    INSTALLED_APPS = [
        'django.contrib.staticfiles',
        'core',
    ]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
] if not LANDING_ONLY else [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        # 'APP_DIRS': True,
        'OPTIONS': {
            "loaders": [
                (
                    "django.template.loaders.filesystem.Loader",
                    # [BASE_DIR / "templates"],
                ),
                'django.template.loaders.app_directories.Loader',
            ],
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

if LANDING_ONLY:
    # In landing-only mode, remove context processors for apps that are not installed.
    TEMPLATES[0]['OPTIONS']['context_processors'] = [p for p in TEMPLATES[0]['OPTIONS']['context_processors'] if 'auth' not in p and 'messages' not in p]

WSGI_APPLICATION = 'config.wsgi.application'


if not LANDING_ONLY:
    # Database
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('PGDATABASE', 'digital_minimalist_db'),
            'USER': os.getenv('PGUSER', 'postgres'),
            'PASSWORD': os.getenv('PGPASSWORD', 'postgres'),
            'HOST': os.getenv('PGHOST', 'localhost'),
            'PORT': os.getenv('PGPORT', '5432'),
        }
    }

    # Use DATABASE_URL if provided (for production)
    if os.getenv('DATABASE_URL'):
        DATABASES['default'] = dj_database_url.parse(os.getenv('DATABASE_URL'))

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Site Configuration
# SITE_DOMAIN is the domain name of the site, e.g. "example.com"
# SITE_ID is the ID of the Site object in the database
# SITE_NAME is the name of the site, e.g. "My Website"
# ALLOWED_HOSTS is a list of host/domain names that the Django server can serve.
# CSRF_TRUSTED_ORIGINS is a list of allowed origins for CSRF checks.
SITE_ID = int(os.getenv('SITE_ID', 1))

# convenience URLs, invented by us.
SITE_NAME = os.getenv('SITE_NAME', 'Intentional Tech')
SITE_DOMAIN = os.getenv('SITE_DOMAIN')

# incoming traffic and frontend
ALLOWED_HOSTS = [host.strip() for host in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if host.strip()]
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if origin.strip()]

def configure_site_settings(site_domain, allowed_hosts, csrf_trusted_origins):
    """
    Consolidates site configuration logic.
    1. Infers SITE_DOMAIN if missing.
    2. Adds SITE_DOMAIN to ALLOWED_HOSTS.
    3. Adds ALLOWED_HOSTS to CSRF_TRUSTED_ORIGINS.
    """
    # 1. Infer SITE_DOMAIN if not set
    if not site_domain:
        site_domain = 'localhost:8000'
        for host in allowed_hosts:
            if host not in ['*', 'localhost', '127.0.0.1']:
                site_domain = host
                break
    
    # 2. Ensure SITE_DOMAIN is in ALLOWED_HOSTS
    if site_domain:
        # Handle schemes and ports
        parse_target = site_domain if '://' in site_domain else f'http://{site_domain}'
        try:
            parsed = urlparse(parse_target)
            domain_host = parsed.netloc.rsplit(':', 1)[0] if parsed.port else parsed.netloc
            
            if domain_host and domain_host not in allowed_hosts:
                allowed_hosts.insert(0, domain_host)
        except ValueError:
            pass

    # 3. Sync ALLOWED_HOSTS to CSRF_TRUSTED_ORIGINS
    for host in allowed_hosts:
        if host not in ['*', 'localhost', '127.0.0.1']:
            origin = f'https://{host}'
            if origin not in csrf_trusted_origins:
                csrf_trusted_origins.append(origin)
                
    return site_domain, allowed_hosts, csrf_trusted_origins

SITE_DOMAIN, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS = configure_site_settings(SITE_DOMAIN, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS)

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django Allauth Configuration
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Django Allauth Settings (updated to new format)
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'  # Set to 'mandatory' in production if desired
ACCOUNT_UNIQUE_EMAIL = True
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
ACCOUNT_SIGNUP_REDIRECT_URL = '/'
ACCOUNT_FORMS = {
    'signup': 'accounts.forms.FullSignupForm',
}
ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False

# passwords!
# ACCOUNT_SIGNUP_FIELDS = ['email*', "password1*"]
# ACCOUNT_LOGIN_BY_CODE_ENABLED = False
# ACCOUNT_LOGIN_BY_CODE_REQUIRED = False

# passwordless
ACCOUNT_SIGNUP_FIELDS = ['email*']
ACCOUNT_LOGIN_BY_CODE_ENABLED = True
ACCOUNT_LOGIN_BY_CODE_REQUIRED = True

# Email Configuration
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')

EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@example.com')

# Stripe Configuration
STRIPE_ENABLED = os.getenv('STRIPE_ENABLED', 'True') == 'True'
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')

# WhiteNoise Configuration
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'payments': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'accounts': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'cohorts': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}


# Django Q Configuration
Q_CLUSTER = {
    'name': 'digital_minimalist',
    'workers': 4,
    'recycle': 500,
    'timeout': 60,
    'compress': True,
    'save_limit': 250,
    'queue_limit': 500,
    'cpu_affinity': 1,
    'label': 'Django Q',
    'orm': 'default',  # Use Django ORM (Database) as the broker
}

# Django Q Email Setup
Q2_EMAIL_BACKEND = EMAIL_BACKEND  # The actual backend (SMTP/Console)
EMAIL_BACKEND = 'django_q2_email_backend.backends.Q2EmailBackend'  # The wrapper that queues emails

SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN != "":
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
        ],
        # Add data like request headers and IP for users,
        # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
        send_default_pii=os.getenv("SENTRY_SEND_DEFAULT_PII", "True") == "True",
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for tracing.
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
        # Set profile_session_sample_rate to 1.0 to profile 100%
        # of profile sessions.
        profile_session_sample_rate=float(os.getenv("SENTRY_PROFILE_SESSION_SAMPLE_RATE", "0.0")),
        # Set profile_lifecycle to "trace" to automatically
        # run the profiler on when there is an active transaction
        profile_lifecycle="trace",
    )
