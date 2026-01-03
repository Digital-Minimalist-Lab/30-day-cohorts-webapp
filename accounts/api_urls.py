from django.urls import path
from .api import update_profile_preferences

app_name = 'accounts_api'

urlpatterns = [
    path('preferences/', update_profile_preferences, name='update_preferences'),
    path('email-reminders/', update_profile_preferences, name='toggle_email_reminders'),
]
