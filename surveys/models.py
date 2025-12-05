from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()



class Survey(models.Model):
    """A collection of questions, like 'Entry Survey' or 'Daily Check-in'."""
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, help_text="A unique slug for identifying the survey type (e.g., 'entry', 'daily-checkin').")
    description = models.TextField(blank=True)
    title_template = models.CharField(max_length=255, blank=True, default="{survey_name}", help_text="A template for the page title. Available placeholders: {survey_name}, {due_date}, {week_number}.")
    
    
    """
    Purposes are used to edit behaviour and UI for certain pages.
    - DAILY_CHECKIN is used to collect summaries and show it in the accounts profile view.
    - EXIT is used to collect the ENTRY data, and show it when presenting the EXIT survey.
    - WEEKLY_REFLECTION and DAILY_CHECKIN used to special-case which summary view is presented in their "list" form.
    """
    class Purpose(models.TextChoices):
        GENERIC = 'GENERIC', _('Generic')
        ENTRY = 'ENTRY', _('Entry Survey')
        EXIT = 'EXIT', _('Exit Survey')
        DAILY_CHECKIN = 'DAILY_CHECKIN', _('Daily Check-in')
        WEEKLY_REFLECTION = 'WEEKLY_REFLECTION', _('Weekly Reflection')

    purpose = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.GENERIC, help_text="The role of this survey in the cohort lifecycle.")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def title(self):
        return self.title_template if self.title_template is not "" else self.name
 
class Question(models.Model):
    """A single question within a survey."""
    class QuestionType(models.TextChoices):
        TEXT = 'text', _('Text (single line)')
        TEXTAREA = 'textarea', _('Text Area (multi-line)')
        INTEGER = 'integer', _('Integer')
        RADIO = 'radio', _('Radio Select')

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='questions')
    key = models.CharField(max_length=100, help_text="A unique key for this question within the survey. May be used in templates.")
    text = models.CharField(max_length=500, help_text="The question text presented to the user.")
    question_type = models.CharField(max_length=20, choices=QuestionType.choices, default=QuestionType.TEXT)
    order = models.PositiveIntegerField(default=0, help_text="The order in which the question appears in the survey.")
    is_required = models.BooleanField(default=True)
    # For radio/select choices, stored as JSON: {"1": "Low", "5": "High"}
    choices = models.JSONField(blank=True, null=True, help_text="JSON object for choices if question_type is 'radio'.")

    class Meta:
        ordering = ['survey', 'order']
        unique_together = ['survey', 'key']

    def __str__(self) -> str:
        return f"{self.survey.name} - {self.text[:50]}"


class SurveySubmission(models.Model):
    """A user's submission for a specific survey."""
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='submissions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='survey_submissions')
    cohort = models.ForeignKey('cohorts.Cohort', on_delete=models.CASCADE, related_name='survey_submissions')
    completed_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True, help_text="The specific due date of the task this submission fulfills.")

    class Meta:
        ordering = ['-completed_at']

    def __str__(self) -> str:
        return f"Submission for {self.survey.name} by {self.user.email} on {self.completed_at.strftime('%Y-%m-%d')}"

    @property
    def week_number(self) -> int | None:
        """Calculate the week number of the submission relative to the cohort start date."""
        if not self.cohort.start_date:
            return None
        days_since_start = (self.due_date - self.cohort.start_date).days
        return (days_since_start // 7) + 1

    def to_dict(self):        
        answers = {ans.question.key: ans.value for ans in self.answers.all()}
        
        data = {
            'cohort': self.cohort.name,
            'survey_name': self.survey.name,
            'survey_purpose': self.survey.purpose,
            'completed_at': self.completed_at.isoformat(),
            'answers': answers,
        }
        if self.due_date:
            data['due_date'] = self.due_date.isoformat()
        if self.week_number:
            data['week_number'] = self.week_number
        return data



class Answer(models.Model):
    """A user's answer to a specific question in a submission."""
    submission = models.ForeignKey(SurveySubmission, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    value = models.TextField()

    class Meta:
        unique_together = ['submission', 'question']

    def __str__(self):
        return f"Answer to '{self.question.key}' in submission {self.submission.id}"
