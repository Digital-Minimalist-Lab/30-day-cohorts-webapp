from django.contrib import admin
from .models import Survey, Question, SurveySubmission, Answer
from cohorts.models import UserSurveyResponse
from cohorts.tasks import find_due_date

class QuestionInline(admin.TabularInline):
    """
    Allows for inline editing of Questions within the Survey admin page.
    """
    model = Question
    extra = 1
    ordering = ['order']
    fields = ('order', 'key', 'text', 'question_type', 'is_required', 'choices')
    list_display = ('order', 'text', 'question_type', 'is_required')
    # A simple way to suggest a key from the text, though it won't auto-populate dynamically.
    # For a better UX, custom JavaScript would be needed.
    description = "Define the questions for this survey in the order they should appear."


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    """
    Admin view for Surveys, with inline Questions.
    """
    list_display = ('name', 'slug', 'created_at')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [QuestionInline]

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
