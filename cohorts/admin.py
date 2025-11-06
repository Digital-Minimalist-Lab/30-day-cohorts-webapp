from django.contrib import admin
from .models import Cohort, Enrollment


@admin.register(Cohort)
class CohortAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'price_cents', 'is_active']
    list_filter = ['is_active', 'start_date']
    search_fields = ['name']
    date_hierarchy = 'start_date'


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['user', 'cohort', 'paid_at', 'enrolled_at']
    list_filter = ['cohort', 'paid_at']
    search_fields = ['user__email', 'cohort__name']
    date_hierarchy = 'enrolled_at'

