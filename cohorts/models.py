from __future__ import annotations
import json
from typing import Optional

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from surveys.models import SurveySubmission, Survey

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
        cohorts_with_seats = [c for c in joinable_cohorts if not c.is_full()]
        return cohorts_with_seats


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

    onboarding_survey = models.ForeignKey(
        Survey,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='onboarding_cohorts',
        help_text="The survey presented during onboarding (e.g. Entry Survey)."
    )

    class Meta:
        ordering = ['-start_date']

    def __str__(self) -> str:
        return f"{self.name} ({self.start_date} to {self.end_date})"

    def pending_enrollments(self) -> int:
        """Count of pending enrollments."""
        return self.enrollments.filter(status='pending').count()
    
    def active_enrollments(self) -> int:
        """Count of active enrollments."""
        return self.enrollments.filter(status__in=['paid', 'free']).count()

    def seats_available(self) -> Optional[int]:
        """Return remaining seats or None if unlimited."""
        if self.max_seats is None:
            return None
        enrolled_count = self.active_enrollments()
        return max(0, self.max_seats - enrolled_count)

    def is_full(self) -> bool:
        """Check if cohort has reached seat capacity."""
        seats_available = self.seats_available()
        if seats_available is None:
            return False
        return seats_available <= 0

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
    slug = models.SlugField(max_length=200, help_text="URL-friendly identifier for this task (e.g., 'daily-checkin', 'week-1-reflection'). Unique within cohort.")

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
        unique_together = [['cohort', 'survey'], ['cohort', 'slug']]
        ordering = ['cohort', 'frequency']

    def __str__(self):
        return f"{self.slug} ({self.survey.name} - {self.get_frequency_display()}) for {self.cohort.name}"

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


class UserSurveyResponse(models.Model):
    """A user's submission for a specific survey task instance."""
    submission = models.OneToOneField(SurveySubmission, on_delete=models.CASCADE, related_name='user_response')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='survey_submissions')
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name='survey_submissions')
    scheduler = models.ForeignKey(TaskScheduler, on_delete=models.CASCADE, related_name='responses')
    task_instance_id = models.IntegerField(help_text="Sequential instance number for this scheduler's tasks (0-indexed).")

    class Meta:
        ordering = ['-submission__completed_at']
        unique_together = [['user', 'cohort', 'scheduler', 'task_instance_id']]

    def __str__(self) -> str:
        return f"Submission for {self.submission.survey.name} by {self.user.email} on {self.submission.completed_at.strftime('%Y-%m-%d')}"

    def to_dict(self):
        answers = {ans.question.key: ans.value for ans in self.submission.answers.all()}

        data = {
            'cohort': self.cohort.name,
            'survey_name': self.submission.survey.name,
            'completed_at': self.submission.completed_at.isoformat(),
            'task_instance_id': self.task_instance_id,
            'answers': answers,
        }
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
