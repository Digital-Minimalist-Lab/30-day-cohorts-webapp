from .base import *

DEBUG = True

# Console email backend for development
Q2_EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

ALLOWED_HOSTS = ['*']