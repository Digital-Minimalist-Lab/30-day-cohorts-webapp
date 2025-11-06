from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'timezone', 'email_daily_reminder', 'email_weekly_reminder', 'created_at']
    list_filter = ['email_daily_reminder', 'email_weekly_reminder', 'timezone']
    search_fields = ['user__email']

