from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()


class EntrySurvey(models.Model):
    """Baseline survey completed at cohort start."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='entry_surveys')
    cohort = models.ForeignKey('cohorts.Cohort', on_delete=models.CASCADE, related_name='entry_surveys')
    mood_1to5 = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Mood rating from 1 (low) to 5 (high)"
    )
    baseline_screentime_min = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Baseline daily screen time in minutes"
    )
    intention_text = models.TextField(help_text="Why are you interested in participating?")
    challenge_text = models.TextField(
        blank=True,
        help_text="Name one thing you would like to reclaim"
    )
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'cohort']
        ordering = ['-completed_at']

    def __str__(self) -> str:
        return f"Entry Survey - {self.user.email} - {self.cohort.name}"


class ExitSurvey(models.Model):
    """Final survey completed at cohort end."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exit_surveys')
    cohort = models.ForeignKey('cohorts.Cohort', on_delete=models.CASCADE, related_name='exit_surveys')
    mood_1to5 = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Final mood rating from 1 (low) to 5 (high)"
    )
    final_screentime_min = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Final daily screen time in minutes"
    )
    wins_text = models.TextField(help_text="What were your wins?")
    insight_text = models.TextField(help_text="What insights did you gain?")
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'cohort']
        ordering = ['-completed_at']

    def __str__(self) -> str:
        return f"Exit Survey - {self.user.email} - {self.cohort.name}"

