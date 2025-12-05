from django.db import models
from django.contrib.auth import get_user_model
import pytz

User = get_user_model()

TIMEZONE_CHOICES = [(tz, tz) for tz in pytz.common_timezones]


class UserProfile(models.Model):
    """Extended user profile with email preferences and timezone."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    email_daily_reminder = models.BooleanField(
        default=False,
        help_text="Opt-in for daily check-in reminders"
    )
    email_weekly_reminder = models.BooleanField(
        default=False,
        help_text="Opt-in for weekly reflection reminders"
    )
    timezone = models.CharField(
        max_length=50,
        choices=TIMEZONE_CHOICES,
        default='UTC',
        help_text="User's timezone for accurate daily check-in dates"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Profile for {self.user.email}"


    def to_dict(self):
        return {
            'timezone': self.timezone,
            'email_daily_reminder': self.email_daily_reminder,
            'email_weekly_reminder': self.email_weekly_reminder,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }