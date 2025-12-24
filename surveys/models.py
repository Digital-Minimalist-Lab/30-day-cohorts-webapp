from __future__ import annotations
from typing import TYPE_CHECKING

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.functional import cached_property
from django.utils.text import slugify

if TYPE_CHECKING:
    from typing import Self

class Survey(models.Model):
    """A collection of questions, like 'Entry Survey' or 'Daily Check-in'."""
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, help_text="A unique slug for identifying the survey type (e.g., 'entry', 'daily-checkin').")
    description = models.TextField(blank=True)
    title_template = models.CharField(max_length=255, blank=True, default="{survey_name}", help_text="A template for the page title. Available placeholders: {survey_name}, {due_date}, {week_number}.")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def title(self):
        return self.title_template if self.title_template != "" else self.name

    def to_design_dict(self, include_questions: bool = True) -> dict:
        """Export this survey to a JSON-serializable dict for cohort design."""
        data = {
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "title_template": self.title_template,
        }
        if include_questions:
            data["questions"] = [
                q.to_design_dict() for q in self.questions.all().order_by('order')
            ]
        return data

    @classmethod
    def from_design_dict(cls, data: dict, save: bool = False) -> Self:
        """
        Create a Survey instance from a design dict.
        
        Args:
            data: The survey design dict
            save: If True, saves the survey and creates questions immediately.
                  If False, stores questions in _pending_questions for later creation.
        """
        survey = cls(
            slug=data.get("slug") or slugify(data["name"]),
            name=data["name"],
            description=data.get("description", ""),
            title_template=data.get("title_template", "{survey_name}"),
        )
        
        if save:
            survey.save()
            # Import here to avoid circular import at module level
            from surveys.models import Question
            for i, q_data in enumerate(data.get("questions", [])):
                Question.from_design_dict(survey, q_data, order=i).save()
        else:
            # Store for later creation
            survey._pending_questions = data.get("questions", [])
        
        return survey

    def create_pending_questions(self):
        """Create questions from _pending_questions if they exist."""
        pending = getattr(self, '_pending_questions', None)
        if pending:
            for i, q_data in enumerate(pending):
                Question.from_design_dict(self, q_data, order=i).save()
            self._pending_questions = None


class Question(models.Model):
    """A single question within a survey."""
    class QuestionType(models.TextChoices):
        TEXT = 'text', _('Text (single line)')
        TEXTAREA = 'textarea', _('Text Area (multi-line)')
        INTEGER = 'integer', _('Integer')
        DECIMAL = 'decimal', _('Decimal')
        RADIO = 'radio', _('Radio Select')
        INFO = 'info', _('Information (display only)')

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='questions')
    key = models.CharField(max_length=100, help_text="A unique key for this question within the survey. May be used in templates.")
    text = models.CharField(max_length=3000, help_text="The question text presented to the user.")
    question_type = models.CharField(max_length=20, choices=QuestionType.choices, default=QuestionType.TEXT)
    section = models.CharField(
        max_length=200, 
        blank=True, 
        default="",
        help_text="Section header. Questions with the same section are grouped together visually."
    )
    order = models.PositiveIntegerField(default=0, help_text="The order in which the question appears in the survey.")
    is_required = models.BooleanField(default=True)
    # For radio/select choices, stored as JSON: {"1": "Low", "5": "High"}
    choices = models.JSONField(blank=True, null=True, help_text="JSON object for choices if question_type is 'radio'.")

    class Meta:
        ordering = ['survey', 'order']
        unique_together = ['survey', 'key']

    def __str__(self) -> str:
        return f"{self.survey.name} - {self.text[:50]}"

    def to_design_dict(self) -> dict:
        """Export this question to a JSON-serializable dict for cohort design."""
        data = {
            "key": self.key,
            "text": self.text,
            "type": self.question_type,
            "is_required": self.is_required,
            "order": self.order,
        }
        # Only include optional fields if they have values
        if self.section:
            data["section"] = self.section
        if self.choices:
            data["choices"] = self.choices
        return data

    @classmethod
    def from_design_dict(cls, survey: Survey, data: dict, order: int = 0) -> Self:
        """
        Create a Question instance from a design dict.
        Note: Does NOT save to database - caller must save after survey is saved.
        """
        return cls(
            survey=survey,
            key=data["key"],
            text=data["text"],
            question_type=data.get("type", cls.QuestionType.TEXT),
            section=data.get("section", ""),
            order=data.get("order", order),
            is_required=data.get("is_required", True),
            choices=data.get("choices"),
        )


class SurveySubmission(models.Model):
    """A user's submission for a specific survey."""
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='submissions')
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-completed_at']

    def __str__(self) -> str:
        return f"Submission for {self.survey.name} on {self.completed_at.strftime('%Y-%m-%d')}"

    @cached_property
    def answer_dict(self):
        """
        Returns the submission's answers as a dictionary of {question_key: answer_value}.
        This is most efficient when `answers` and `answers__question` have been prefetched.
        """
        return {answer.question.key: answer.value for answer in self.answers.all()}

class Answer(models.Model):
    """A user's answer to a specific question in a submission."""
    submission = models.ForeignKey(SurveySubmission, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    value = models.TextField()

    class Meta:
        unique_together = ['submission', 'question']

    def __str__(self):
        return f"Answer to '{self.question.key}' in submission {self.submission.id}"
