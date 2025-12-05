from django.contrib import admin
from .models import Survey, Question, SurveySubmission, Answer

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
    list_display = ('name', 'slug', 'purpose', 'created_at')
    list_filter = ('purpose',)
    search_fields = ('name', 'slug', 'purpose')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [QuestionInline]


class AnswerInline(admin.TabularInline):
    """
    Read-only inline view of Answers within the SurveySubmission admin page.
    """
    model = Answer
    extra = 0
    readonly_fields = ('question', 'value')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SurveySubmission)
class SurveySubmissionAdmin(admin.ModelAdmin):
    list_display = ('survey', 'user', 'cohort', 'due_date', 'completed_at')
    list_filter = ('survey', 'cohort', 'completed_at')
    search_fields = ('user__email', 'cohort__name', 'survey__name')
    date_hierarchy = 'completed_at'
    inlines = [AnswerInline]
    readonly_fields = ('survey', 'user', 'cohort')
