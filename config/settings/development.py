from .base import *

DEBUG = True

# Allow all hosts in development
ALLOWED_HOSTS = ['*']

# Console email backend for development
Q2_EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

