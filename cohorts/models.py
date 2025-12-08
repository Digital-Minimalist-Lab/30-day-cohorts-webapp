from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.utils import timezone
from typing import Optional
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _

from surveys.models import SurveySubmission, Survey

User = get_user_model()

class CohortManager(models.Manager):
    def get_active(self):
        """Returns active cohorts that have started but not ended."""
        today = timezone.now().date()
        return self.filter(is_active=True, start_date__lte=today, end_date__gte=today)

    def get_upcoming(self):
        """Returns active cohorts that have not started yet."""
        today = timezone.now().date()
        return self.filter(is_active=True, start_date__gt=today).order_by('start_date')

    def get_joinable(self):
        """
        Returns active cohorts that started within the last 7 days.
        This mirrors the logic in the Cohort.can_join() method.
        """
        today = timezone.now().date()
        one_week_ago = today - timezone.timedelta(days=7)
        return self.filter(is_active=True, start_date__gte=one_week_ago, start_date__lte=today).order_by('-start_date')


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

    def can_join(self) -> bool:
        """Check if users can still join (within 7 days of start and seats available)."""
        today = timezone.now().date()
        days_since_start = (today - self.start_date).days
        return days_since_start <= 7 and self.is_active and not self.is_full()


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
        START = 'start', _('From Cohort Start')
        END = 'end', _('From Cohort End')

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
    offset_from = models.CharField(max_length=10, choices=OffsetFrom.choices, blank=True, null=True, help_text="For ONCE frequency. The reference point for the offset.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['cohort', 'survey']
        ordering = ['cohort', 'frequency']

    def __str__(self):
        return f"{self.survey.name} schedule for {self.cohort.name} ({self.get_frequency_display()})"
    

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
