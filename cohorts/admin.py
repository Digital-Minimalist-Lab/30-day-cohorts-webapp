import json
from datetime import datetime
from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import redirect

from .models import Cohort, Enrollment, TaskScheduler, UserSurveyResponse
from django.contrib import admin
from .models import Cohort, Enrollment, EmailSendLog
from cohorts.models import TaskScheduler, UserSurveyResponse


class TaskSchedulerInline(admin.TabularInline):
    model = TaskScheduler
    extra = 1
    fields = ('survey', 'frequency', 'is_cumulative', 'day_of_week', 'offset_days', 'offset_from', 'task_title_template', 'task_description_template')


@admin.register(Cohort)
class CohortAdmin(admin.ModelAdmin):
    list_display = ['name', 'enrollment_start_date', 'enrollment_end_date', 'start_date', 'end_date', 'minimum_price_cents', 'is_paid', 'seats_display', 'is_active']
    list_filter = ['is_active', 'is_paid', 'start_date']
    search_fields = ['name']
    date_hierarchy = 'start_date'
    actions = ['export_cohort_design']  # Only export action
    add_form_template = 'admin/cohorts/cohort_add_form.html'
    
    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'enrollment_start_date', 'enrollment_end_date', 'is_active', 'start_date', 'end_date']
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

    @admin.action(description='📥 Export selected cohort as JSON')
    def export_cohort_design(self, request, queryset):
        """Export cohort design - downloads immediately."""
        if queryset.count() > 1:
            self.message_user(
                request,
                "Please select only one cohort to export.",
                level=messages.WARNING
            )
            return
        
        cohort = queryset.first()
        response = HttpResponse(
            cohort.to_json(indent=2),
            content_type='application/json'
        )
        filename = f"{cohort.name.lower().replace(' ', '_')}_design.json"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    def add_view(self, request, form_url='', extra_context=None):
        """Override add view to handle JSON upload for quick import."""
        
        # Check if JSON file was uploaded
        if request.method == 'POST' and 'json_file' in request.FILES:
            try:
                json_file = request.FILES['json_file']
                start_date_str = request.POST.get('import_start_date')
                name_override = request.POST.get('import_name', '').strip() or None
                update_surveys = request.POST.get('import_update_surveys') == 'on'
                
                if not start_date_str:
                    raise ValueError("Start date is required")
                
                # Parse and create
                data = json.load(json_file)
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                
                cohort = Cohort.from_design_dict(
                    data,
                    start_date=start_date,
                    name_override=name_override,
                    update_existing_surveys=update_surveys
                )
                
                self.message_user(
                    request,
                    f"✅ Successfully imported cohort '{cohort.name}' (ID: {cohort.pk})",
                    messages.SUCCESS
                )
                # Redirect to change page for the new cohort
                return redirect('admin:cohorts_cohort_change', cohort.pk)
                
            except Exception as e:
                self.message_user(
                    request,
                    f"❌ Import failed: {str(e)}",
                    messages.ERROR
                )
        
        # Continue with normal add view
        return super().add_view(request, form_url, extra_context)


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


@admin.register(EmailSendLog)
class EmailSendLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'email_type', 'recipient_email', 'idempotency_key']
    list_filter = ['email_type', 'created_at']
    search_fields = ['recipient_email', 'idempotency_key']
    readonly_fields = [
        'idempotency_key',
        'recipient_email',
        'recipient_user',
        'email_type',
        'created_at',
    ]
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False  # Logs are created programmatically only

    def has_change_permission(self, request, obj=None):
        return False  # Logs are immutable
