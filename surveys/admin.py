from django.contrib import admin
from .models import EntrySurvey, ExitSurvey


@admin.register(EntrySurvey)
class EntrySurveyAdmin(admin.ModelAdmin):
    list_display = ['user', 'cohort', 'mood_1to5', 'baseline_screentime_min', 'completed_at']
    list_filter = ['cohort', 'completed_at']
    search_fields = ['user__email', 'cohort__name']
    date_hierarchy = 'completed_at'
    readonly_fields = ['completed_at']


@admin.register(ExitSurvey)
class ExitSurveyAdmin(admin.ModelAdmin):
    list_display = ['user', 'cohort', 'mood_1to5', 'final_screentime_min', 'completed_at']
    list_filter = ['cohort', 'completed_at']
    search_fields = ['user__email', 'cohort__name']
    date_hierarchy = 'completed_at'
    readonly_fields = ['completed_at']

