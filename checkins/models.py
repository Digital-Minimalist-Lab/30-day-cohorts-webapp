from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()


class DailyCheckin(models.Model):
    """
    Daily 5-step keystone habit reflection:
    1. Rate your mood (1-5)
    2. Rate satisfaction with digital use today (1-5)
    3. Screen time in minutes (estimated or actual)
    4. One thing you're proud of that replaced scrolling
    5a. If you slipped into digital use, how? (optional)
    5b. 1-2 sentences about how today went
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_checkins')
    cohort = models.ForeignKey('cohorts.Cohort', on_delete=models.CASCADE, related_name='daily_checkins')
    date = models.DateField()
    
    # Step 1: Mood
    mood_1to5 = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="How do you feel today? (1-5)"
    )
    
    # Step 2: Digital satisfaction
    digital_satisfaction_1to5 = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Satisfaction with your digital use today (1-5)"
    )
    
    # Step 3: Screen time
    screentime_min = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Screen time in minutes (estimated or actual)"
    )
    
    # Step 4: Proud moment
    proud_moment_text = models.TextField(
        help_text="One thing you're proud of doing that replaced scrolling"
    )
    
    # Step 5a: Digital slip (optional)
    digital_slip_text = models.TextField(
        blank=True,
        help_text="If you slipped into digital use in any way, how? (optional)"
    )
    
    # Step 5b: Reflection
    reflection_text = models.TextField(
        help_text="1-2 sentences about how today went"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'cohort', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['user', 'cohort', 'date']),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} - {self.cohort.name} - {self.date}"


class WeeklyReflection(models.Model):
    """Weekly reflection and goal setting."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='weekly_reflections')
    cohort = models.ForeignKey('cohorts.Cohort', on_delete=models.CASCADE, related_name='weekly_reflections')
    week_index = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(4)],
        help_text="Week number (1-4)"
    )
    goal_text = models.TextField(help_text="What's your intention for this week?")
    reflection_text = models.TextField(
        blank=True,
        help_text="Optional reflection on last week"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'cohort', 'week_index']
        ordering = ['week_index']
        indexes = [
            models.Index(fields=['user', 'cohort', 'week_index']),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} - {self.cohort.name} - Week {self.week_index}"

