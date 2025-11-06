from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from datetime import timedelta

User = get_user_model()


class Cohort(models.Model):
    """A 30-day digital declutter cohort."""
    name = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    price_cents = models.IntegerField(
        default=1000,
        validators=[MinValueValidator(0)],
        help_text="Price in cents (e.g., 1000 = $10.00)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this cohort is currently accepting enrollments"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self) -> str:
        return f"{self.name} ({self.start_date} to {self.end_date})"

    def can_join(self) -> bool:
        """Check if users can still join (within 7 days of start)."""
        from django.utils import timezone
        today = timezone.now().date()
        days_since_start = (today - self.start_date).days
        return days_since_start <= 7 and self.is_active


class Enrollment(models.Model):
    """User enrollment in a cohort."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name='enrollments')
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When payment was completed (null if self-hosted/payment disabled)"
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'cohort']
        ordering = ['-enrolled_at']

    def __str__(self) -> str:
        return f"{self.user.email} - {self.cohort.name}"

