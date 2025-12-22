from __future__ import annotations
import json
from datetime import date, timedelta
from typing import TYPE_CHECKING, Optional

from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from surveys.models import SurveySubmission, Survey

if TYPE_CHECKING:
    from typing import Self

User = get_user_model()

class CohortManager(models.Manager):
    def get_joinable(self):
        """
        Returns active, non-full cohorts that are within their joining period.
        This mirrors the logic in the Cohort.can_join() method.
        """
        today = timezone.now().date()

        # A cohort is joinable if it's within an explicit enrollment period...
        within_enrollment_period = Q(
            enrollment_start_date__lte=today,
            enrollment_end_date__gte=today
        )
        # ...or if no specific enrollment period is defined.
        no_enrollment_period = Q(
            enrollment_start_date__isnull=True,
            enrollment_end_date__isnull=True
        )

        joinable_cohorts = self.filter(
            Q(within_enrollment_period | no_enrollment_period),
            is_active=True,
        )

        # Exclude full cohorts in Python, as this is simpler than a complex subquery.
        return [c for c in joinable_cohorts if not c.is_full()]


class Cohort(models.Model):
    """A 30-day digital declutter cohort."""
    name = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    minimum_price_cents = models.IntegerField(
        default=1000,
        validators=[MinValueValidator(0)],
        help_text="Minimum price in cents (e.g., 1000 = $10.00)"
    )
    is_paid = models.BooleanField(
        default=True,
        help_text="Whether this cohort requires payment"
    )
    max_seats = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Maximum number of seats (null = unlimited)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this cohort is currently accepting enrollments"
    )
    enrollment_start_date = models.DateField(
        null=True, blank=True, help_text="The first day users can join the cohort."
    )
    enrollment_end_date = models.DateField(
        null=True, blank=True, help_text="The last day users can join the cohort."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CohortManager() # Add the custom manager

    class Meta:
        ordering = ['-start_date']

    def __str__(self) -> str:
        return f"{self.name} ({self.start_date} to {self.end_date})"

    def seats_available(self) -> Optional[int]:
        """Return remaining seats or None if unlimited."""
        if self.max_seats is None:
            return None
        enrolled_count = self.enrollments.count()
        return max(0, self.max_seats - enrolled_count)

    def is_full(self) -> bool:
        """Check if cohort has reached seat capacity."""
        if self.max_seats is None:
            return False
        return self.enrollments.count() >= self.max_seats

    def to_design_dict(self) -> dict:
        """
        Export full cohort design (template + surveys + schedules) to JSON-serializable dict.
        
        This captures the "blueprint" of a cohort that can be used to create new cohorts.
        """
        return {
            "cohort_template": {
                "name": self.name,
                "duration_days": (self.end_date - self.start_date).days,
                "is_paid": self.is_paid,
                "minimum_price_cents": self.minimum_price_cents,
                "max_seats": self.max_seats,
            },
            "surveys": [
                {
                    **scheduler.survey.to_design_dict(),
                    "schedule": scheduler.to_design_dict(),
                }
                for scheduler in self.task_schedulers.select_related('survey').prefetch_related('survey__questions')
            ]
        }

    def to_json(self, indent: int = 2) -> str:
        """Export cohort design to a formatted JSON string."""
        return json.dumps(self.to_design_dict(), indent=indent)

    @classmethod
    def validate_design_dict(cls, data: dict) -> list[str]:
        """
        Validate a cohort design dict structure.
        Returns a list of error messages (empty list if valid).
        """
        errors = []
        
        # Check top-level structure
        if "cohort_template" not in data:
            errors.append("Missing 'cohort_template' key")
        else:
            template = data["cohort_template"]
            if "duration_days" not in template:
                errors.append("cohort_template missing 'duration_days'")
            if "name" not in template:
                errors.append("cohort_template missing 'name'")
        
        if "surveys" not in data:
            errors.append("Missing 'surveys' key")
        elif not isinstance(data["surveys"], list):
            errors.append("'surveys' must be a list")
        else:
            for i, survey in enumerate(data["surveys"]):
                prefix = f"surveys[{i}]"
                
                if "slug" not in survey and "name" not in survey:
                    errors.append(f"{prefix}: must have 'slug' or 'name'")
                
                if "questions" not in survey:
                    errors.append(f"{prefix}: missing 'questions'")
                elif not isinstance(survey["questions"], list):
                    errors.append(f"{prefix}: 'questions' must be a list")
                else:
                    for j, q in enumerate(survey["questions"]):
                        q_prefix = f"{prefix}.questions[{j}]"
                        if "key" not in q:
                            errors.append(f"{q_prefix}: missing 'key'")
                        if "text" not in q:
                            errors.append(f"{q_prefix}: missing 'text'")
                        if "type" not in q:
                            errors.append(f"{q_prefix}: missing 'type'")
                        elif q["type"] not in ["text", "textarea", "integer", "radio", "info"]:
                            errors.append(f"{q_prefix}: invalid type '{q['type']}'")
                
                if "schedule" not in survey:
                    errors.append(f"{prefix}: missing 'schedule'")
                else:
                    schedule = survey["schedule"]
                    if "frequency" not in schedule:
                        errors.append(f"{prefix}.schedule: missing 'frequency'")
                    elif schedule["frequency"] not in ["ONCE", "DAILY", "WEEKLY"]:
                        errors.append(f"{prefix}.schedule: invalid frequency '{schedule['frequency']}'")
                    elif schedule["frequency"] == "WEEKLY" and "day_of_week" not in schedule:
                        errors.append(f"{prefix}.schedule: WEEKLY frequency requires 'day_of_week'")
                    elif schedule["frequency"] == "ONCE":
                        if "offset_days" not in schedule:
                            errors.append(f"{prefix}.schedule: ONCE frequency requires 'offset_days'")
                        if "offset_from" not in schedule:
                            errors.append(f"{prefix}.schedule: ONCE frequency requires 'offset_from'")
                        elif schedule["offset_from"] not in TaskScheduler.OffsetFrom.values:
                            errors.append(f"{prefix}.schedule: invalid offset_from '{schedule['offset_from']}'")
        
        return errors

    @classmethod
    def from_json_file(cls, file_path: str, start_date: date, **kwargs) -> Self:
        """
        Load a cohort design from a JSON file and create a cohort.
        
        Args:
            file_path: Path to the JSON file
            start_date: The start date for this cohort instance
            **kwargs: Additional arguments passed to from_design_dict()
        """
        with open(file_path, 'r') as f:
            data = json.load(f)
        return cls.from_design_dict(data, start_date, **kwargs)

    @classmethod
    @transaction.atomic
    def from_design_dict(
        cls,
        data: dict,
        start_date: date,
        name_override: Optional[str] = None,
        update_existing_surveys: bool = False,
        validate: bool = True,
    ) -> Self:
        """
        Create a new cohort from a design dict.
        
        Args:
            data: The cohort design dict (with cohort_template and surveys)
            start_date: The start date for this cohort instance
            name_override: Optional name to use instead of the template name
            update_existing_surveys: If True, update existing surveys with same slug.
                                     If False (default), reuse existing surveys as-is.
            validate: If True (default), validate the dict structure before importing.
        
        Returns:
            The created Cohort instance with all surveys and schedules configured.
        
        Raises:
            ValueError: If validate=True and the dict structure is invalid.
        """
        if validate:
            errors = cls.validate_design_dict(data)
            if errors:
                raise ValueError(f"Invalid cohort design: {'; '.join(errors)}")
        
        template = data["cohort_template"]
        duration_days = template["duration_days"]
        end_date = start_date + timedelta(days=duration_days)
        
        # Create the cohort
        cohort = cls.objects.create(
            name=name_override or template.get("name", f"Cohort starting {start_date}"),
            start_date=start_date,
            end_date=end_date,
            is_paid=template.get("is_paid", False),
            minimum_price_cents=template.get("minimum_price_cents", 0),
            max_seats=template.get("max_seats"),
            is_active=True,
        )
        
        # Create or get surveys and their schedules
        # Note: A post_save signal may create default schedulers, so we use get_or_create
        # and update with the imported schedule settings
        for survey_data in data.get("surveys", []):
            survey = cls._get_or_create_survey(survey_data, update_existing=update_existing_surveys)
            schedule_data = survey_data.get("schedule", {})
            
            # Get existing scheduler (possibly created by signal) or create new one
            scheduler, created = TaskScheduler.objects.get_or_create(
                cohort=cohort,
                survey=survey,
                defaults={
                    "frequency": schedule_data["frequency"],
                    "is_cumulative": schedule_data.get("is_cumulative", False),
                    "task_title_template": schedule_data.get("task_title_template", ""),
                    "task_description_template": schedule_data.get("task_description_template", ""),
                    "day_of_week": schedule_data.get("day_of_week"),
                    "offset_days": schedule_data.get("offset_days"),
                    "offset_from": schedule_data.get("offset_from"),
                }
            )
            
            # If it already existed (from signal), update it with imported settings
            if not created:
                scheduler.frequency = schedule_data["frequency"]
                scheduler.is_cumulative = schedule_data.get("is_cumulative", False)
                scheduler.task_title_template = schedule_data.get("task_title_template", "")
                scheduler.task_description_template = schedule_data.get("task_description_template", "")
                scheduler.day_of_week = schedule_data.get("day_of_week")
                scheduler.offset_days = schedule_data.get("offset_days")
                scheduler.offset_from = schedule_data.get("offset_from")
                scheduler.save()
        
        return cohort

    @staticmethod
    def _get_or_create_survey(survey_data: dict, update_existing: bool = False) -> Survey:
        """Helper to get or create a survey from design data."""
        from django.utils.text import slugify
        from surveys.models import Question
        
        slug = survey_data.get("slug") or slugify(survey_data["name"])
        
        # Check if survey already exists
        existing = Survey.objects.filter(slug=slug).first()
        if existing and not update_existing:
            return existing
        
        if existing and update_existing:
            # Update existing survey
            existing.name = survey_data.get("name", slug)
            existing.description = survey_data.get("description", "")
            existing.purpose = survey_data.get("purpose", Survey.Purpose.GENERIC)
            existing.title_template = survey_data.get("title_template", "{survey_name}")
            existing.save()
            # Delete and recreate questions
            existing.questions.all().delete()
            for i, q_data in enumerate(survey_data.get("questions", [])):
                Question.from_design_dict(existing, q_data, order=i).save()
            return existing
        
        # Create new survey with questions
        return Survey.from_design_dict(survey_data, save=True)


class Enrollment(models.Model):
    """User enrollment in a cohort."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('free', 'Free'),
        ('refunded', 'Refunded'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name='enrollments')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Enrollment status"
    )
    amount_paid_cents = models.IntegerField(
        null=True,
        blank=True,
        help_text="Amount paid in cents (null if free or pending)"
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When payment was completed (null if free or pending)"
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'cohort']
        ordering = ['-enrolled_at']

    def __str__(self) -> str:
        return f"{self.user.email} - {self.cohort.name} ({self.status})"

    def to_dict(self):
        return {
            'cohort': self.cohort.name,
            'enrolled_at': self.enrolled_at.isoformat(),
            'status': self.status,
            'amount_paid_cents': self.amount_paid_cents,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'enrolled_at': self.enrolled_at.isoformat(),
        }
    

class TaskScheduler(models.Model):
    """Defines the rules for when a survey should be presented to a user."""
    class Frequency(models.TextChoices):
        ONCE = 'ONCE', _('Once')
        DAILY = 'DAILY', _('Daily')
        WEEKLY = 'WEEKLY', _('Weekly')

    class OffsetFrom(models.TextChoices):
        ENROLL_START = 'ENROLL_START', _('From Enrollment Start')
        ENROLL_END = 'ENROLL_END', _('From Enrollment End')
        COHORT_START = 'COHORT_START', _('From Cohort Start')
        COHORT_END = 'COHORT_END', _('From Cohort End')

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='schedulers')
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name='task_schedulers', help_text="The cohort this schedule applies to.")

    task_title_template = models.CharField(max_length=200, blank=True, help_text="Template for the task title. Placeholders: {survey_name}, {week_number}, {due_date}. If blank, survey name is used.")
    task_description_template = models.TextField(blank=True, help_text="Template for the task description. Placeholders: {survey_name}, {week_number}, {due_date}. If blank, survey description is used.")

    frequency = models.CharField(max_length=20, choices=Frequency.choices, help_text="How often the task repeats.")
    is_cumulative = models.BooleanField(default=False, help_text="If true, missed tasks will accumulate over time.")

    # Fields for WEEKLY frequency
    day_of_week = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(6)], help_text="For WEEKLY frequency (0=Monday, 1=Tuesday, ..., 6=Sunday).")

    # Fields for ONCE frequency
    offset_days = models.IntegerField(blank=True, null=True, help_text="For ONCE frequency. The number of days to offset from the start/end date.")
    offset_from = models.CharField(max_length=50, choices=OffsetFrom.choices, blank=True, null=True, help_text="For ONCE frequency. The reference point for the offset.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['cohort', 'survey']
        ordering = ['cohort', 'frequency']

    def __str__(self):
        return f"{self.survey.name} schedule for {self.cohort.name} ({self.get_frequency_display()})"

    def to_design_dict(self) -> dict:
        """Export this schedule to a JSON-serializable dict for cohort design."""
        data = {
            "frequency": self.frequency,
            "is_cumulative": self.is_cumulative,
            "task_title_template": self.task_title_template,
            "task_description_template": self.task_description_template,
        }
        # Add frequency-specific fields
        if self.frequency == self.Frequency.WEEKLY:
            data["day_of_week"] = self.day_of_week
        elif self.frequency == self.Frequency.ONCE:
            data["offset_days"] = self.offset_days
            data["offset_from"] = self.offset_from
        return data

    @classmethod
    def from_design_dict(cls, cohort: Cohort, survey: Survey, data: dict) -> Self:
        """Create a TaskScheduler instance from a design dict."""
        return cls(
            cohort=cohort,
            survey=survey,
            frequency=data["frequency"],
            is_cumulative=data.get("is_cumulative", False),
            task_title_template=data.get("task_title_template", ""),
            task_description_template=data.get("task_description_template", ""),
            day_of_week=data.get("day_of_week"),
            offset_days=data.get("offset_days"),
            offset_from=data.get("offset_from"),
        )


class UserSurveyResponse(models.Model):
    """A user's submission for a specific survey."""
    submission = models.ForeignKey(SurveySubmission, on_delete=models.CASCADE, related_name='user_responses')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='survey_submissions')
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name='survey_submissions')
    due_date = models.DateField(null=True, blank=True, help_text="The specific due date of the task this submission fulfills.")

    class Meta:
        ordering = ['-submission__completed_at']

    def __str__(self) -> str:
        return f"Submission for {self.submission.survey.name} by {self.user.email} on {self.submission.completed_at.strftime('%Y-%m-%d')}"

    def to_dict(self):
        answers = {ans.question.key: ans.value for ans in self.submission.answers.all()}

        data = {
            'cohort': self.cohort.name,
            'survey_name': self.submission.survey.name,
            'survey_purpose': self.submission.survey.purpose,
            'completed_at': self.submission.completed_at.isoformat(),
            'answers': answers,
        }
        if self.due_date:
            data['due_date'] = self.due_date.isoformat()
        return data


class EmailSendLogManager(models.Manager):
    """Manager with helper methods for email deduplication."""

    def was_sent(self, idempotency_key: str) -> bool:
        """Check if an email with this key was successfully sent."""
        return self.filter(idempotency_key=idempotency_key).exists()

    def record_sent(
        self,
        idempotency_key: str,
        recipient_email: str,
        email_type: str,
        recipient_user=None,
    ):
        """Record a successfully sent email."""
        return self.create(
            idempotency_key=idempotency_key,
            recipient_email=recipient_email,
            recipient_user=recipient_user,
            email_type=email_type,
        )


class EmailSendLog(models.Model):
    """Tracks successfully sent emails for deduplication."""

    idempotency_key = models.CharField(max_length=255, unique=True)
    recipient_email = models.EmailField()
    recipient_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_logs',
    )
    email_type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = EmailSendLogManager()

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Email Send Log'
        verbose_name_plural = 'Email Send Logs'

    def __str__(self):
        return f"{self.email_type} to {self.recipient_email} at {self.created_at}"
