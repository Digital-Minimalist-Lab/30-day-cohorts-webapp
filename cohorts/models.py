from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from datetime import timedelta
from typing import Optional

User = get_user_model()


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
        from django.utils import timezone
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

