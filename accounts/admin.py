from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'timezone', 'email_product_updates', 'email_daily_reminder', 'created_at']
    list_filter = ['email_product_updates', 'email_daily_reminder', 'timezone']
    search_fields = ['user__email']

