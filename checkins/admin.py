from django.contrib import admin
from .models import DailyCheckin, WeeklyReflection


@admin.register(DailyCheckin)
class DailyCheckinAdmin(admin.ModelAdmin):
    list_display = ['user', 'cohort', 'date', 'mood_1to5', 'digital_satisfaction_1to5', 'screentime_min']
    list_filter = ['cohort', 'date']
    search_fields = ['user__email', 'cohort__name']
    date_hierarchy = 'date'
    readonly_fields = ['created_at', 'updated_at']


@admin.register(WeeklyReflection)
class WeeklyReflectionAdmin(admin.ModelAdmin):
    list_display = ['user', 'cohort', 'week_index', 'created_at']
    list_filter = ['cohort', 'week_index']
    search_fields = ['user__email', 'cohort__name']
    readonly_fields = ['created_at', 'updated_at']

