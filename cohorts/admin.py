from django.contrib import admin
from .models import Cohort, Enrollment
from cohorts.models import TaskScheduler, UserSurveyResponse


class TaskSchedulerInline(admin.TabularInline):
    model = TaskScheduler
    extra = 1
    fields = ('survey', 'frequency', 'is_cumulative', 'day_of_week', 'offset_days', 'offset_from', 'task_title_template', 'task_description_template')

@admin.register(Cohort)
class CohortAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'enrollment_start_date', 'enrollment_end_date', 'minimum_price_cents', 'is_paid', 'seats_display', 'is_active']
    list_filter = ['is_active', 'is_paid', 'start_date']
    search_fields = ['name']
    date_hierarchy = 'start_date'
    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'start_date', 'end_date', 'is_active', 'enrollment_start_date', 'enrollment_end_date']
        }),
        ('Pricing', {
            'fields': ['is_paid', 'minimum_price_cents']
        }),
        ('Capacity', {
            'fields': ['max_seats'],
            'description': 'Leave blank for unlimited seats'
        }),
    ]
    inlines = [TaskSchedulerInline]
    
    def get_inlines(self, request, obj=None):
        """Don't show schedulers on the add page, they are created by a signal."""
        if obj is None:
            return []
        return super().get_inlines(request, obj)

    def seats_display(self, obj):
        """Display seats taken / max seats."""
        enrolled_count = obj.enrollments.count()
        if obj.max_seats is None:
            return f"{enrolled_count} / ∞"
        return f"{enrolled_count} / {obj.max_seats}"
    seats_display.short_description = 'Seats'


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['user', 'cohort', 'status', 'amount_paid_cents', 'paid_at', 'enrolled_at']
    list_filter = ['status', 'cohort', 'paid_at']
    search_fields = ['user__email', 'cohort__name']
    date_hierarchy = 'enrolled_at'
    readonly_fields = ['enrolled_at']


@admin.register(UserSurveyResponse)
class UserSurveyResponseAdmin(admin.ModelAdmin):
    list_display = ('user', 'cohort', 'get_survey_name', 'due_date', 'get_completed_at', 'get_submission_id')
    list_filter = ('cohort', 'due_date')
    search_fields = ('user__email', 'cohort__name', 'submission__survey__name')
    readonly_fields = ('user', 'cohort', 'submission', 'due_date', 'get_completed_at', 'get_submission_id')

    def get_survey_name(self, obj):
        return obj.submission.survey.name if obj.submission else 'N/A'
    get_survey_name.short_description = 'Survey'

    def get_completed_at(self, obj):
        return obj.submission.completed_at if obj.submission else 'N/A'
    get_completed_at.short_description = 'Completed At'

    def get_submission_id(self, obj):
        return obj.submission.id if obj.submission else 'N/A'
    get_submission_id.short_description = 'Submission ID'

    def has_add_permission(self, request):
        return False
