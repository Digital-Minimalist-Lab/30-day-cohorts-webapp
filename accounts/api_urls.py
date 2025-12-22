from django.urls import path
from .api import toggle_email_reminders

app_name = 'accounts_api'

urlpatterns = [
    path('email-reminders/', toggle_email_reminders, name='toggle_email_reminders'),
]
