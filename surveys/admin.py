from django.contrib import admin
from django.utils.html import format_html
from .models import Survey, Question, SurveySubmission, Answer, SurveySection
from cohorts.models import UserSurveyResponse
from cohorts.tasks import find_due_date

class QuestionInline(admin.TabularInline):
    """
    Allows for inline editing of Questions within the Survey admin page.
    """
    model = Question
    extra = 1
    ordering = ['order']
    fields = ('order', 'section', 'key', 'text', 'question_type', 'is_required', 'choices', 'strength')
    list_display = ('order', 'section', 'text', 'question_type', 'is_required')
    # A simple way to suggest a key from the text, though it won't auto-populate dynamically.
    # For a better UX, custom JavaScript would be needed.
    description = "Define the questions for this survey in the order they should appear."

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter the section dropdown to only show sections for this survey."""
        if db_field.name == "section":
            if request.resolver_match and request.resolver_match.kwargs.get('object_id'):
                kwargs["queryset"] = SurveySection.objects.filter(survey_id=request.resolver_match.kwargs.get('object_id'))
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class SurveySectionInline(admin.TabularInline):
    """
    Allows for inline editing of Survey Sections.
    """
    model = SurveySection
    extra = 0
    ordering = ['order']

@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    """
    Admin view for Surveys, with inline Questions.
    """
    list_display = ('name', 'slug', 'created_at', 'preview_link')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [SurveySectionInline, QuestionInline]
    readonly_fields = ('preview_link', 'created_at')
    fields = ('name', 'slug', 'description', 'title_template', 'estimated_time_minutes', 'preview_link', 'created_at')

    def preview_link(self, obj):
        if obj:
            return format_html('<a href="/surveys/{}/" target="_blank">Preview</a>', obj.slug)
        return "-"
    preview_link.short_description = "Preview"

class UserSurveyResponseInline(admin.StackedInline):
    """Allows for inline editing of the UserSurveyResponse."""
    model = UserSurveyResponse
    extra = 1
    max_num = 1
    fields = ('user', 'cohort', 'scheduler', 'task_instance_id')

class AnswerInline(admin.TabularInline):
    """
    Inline view of Answers within the SurveySubmission admin page.
    """
    model = Answer
    extra = 0
    fields = ('question', 'value')
    readonly_fields = ('question',)

    def get_queryset(self, request):
        """Ensure we only show answers that are linked to a question."""
        qs = super().get_queryset(request)
        return qs.filter(question__isnull=False, submission__isnull=False)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SurveySubmission)
class SurveySubmissionAdmin(admin.ModelAdmin):
    list_display = ('survey', 'get_user',  'get_due_date', 'get_cohort', 'completed_at')
    list_filter = ('survey', 'completed_at')
    search_fields = ('survey__name', 'user_response__user__email', 'user_response__cohort__name')
    date_hierarchy = 'completed_at'
    inlines = [UserSurveyResponseInline, AnswerInline]
    readonly_fields = ('completed_at',)

    def get_user(self, obj):
        return obj.user_response.user if hasattr(obj, 'user_response') else 'N/A'
    get_user.short_description = 'User'
    get_user.admin_order_field = 'user_response__user'

    def get_cohort(self, obj):
        return obj.user_response.cohort if hasattr(obj, 'user_response') else 'N/A'
    get_cohort.short_description = 'Cohort'
    get_cohort.admin_order_field = 'user_response__cohort'

    def get_due_date(self, obj):
        return find_due_date(obj.user_response.scheduler, obj.user_response.task_instance_id) if hasattr(obj, 'user_response') else 'N/A'
    get_due_date.short_description = 'Due Date'

    def get_form(self, request, obj=None, **kwargs):
        """Dynamically set readonly_fields for answers."""
        form = super().get_form(request, obj, **kwargs)
        if obj: # If the object is saved and has a survey
            questions = obj.survey.questions.all()
            Answer.objects.bulk_create([Answer(submission=obj, question=q) for q in questions if not obj.answers.filter(question=q).exists() and not q.question_type == Question.QuestionType.INFO], ignore_conflicts=True)
        return form
