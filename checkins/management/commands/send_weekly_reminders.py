from typing import Any
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from cohorts.models import Enrollment
from checkins.models import WeeklyReflection
import pytz


class Command(BaseCommand):
    help = 'Send weekly reflection reminders to opted-in users'

    def handle(self, *args: Any, **options: Any) -> None:
        """Send email reminders for weekly reflections."""
        sent_count = 0
        
        # Get all active enrollments with users who opted in
        enrollments = Enrollment.objects.filter(
            user__profile__email_weekly_reminder=True,
            cohort__is_active=True
        ).select_related('user', 'user__profile', 'cohort')
        
        week_days = {1: 7, 2: 14, 3: 21, 4: 28}
        
        for enrollment in enrollments:
            user = enrollment.user
            cohort = enrollment.cohort
            
            # Get user's today (defensive - get or create profile)
            from accounts.models import UserProfile
            profile, _ = UserProfile.objects.get_or_create(user=user)
            user_tz = pytz.timezone(profile.timezone)
            today = timezone.now().astimezone(user_tz).date()
            
            days_since_start = (today - cohort.start_date).days
            
            # Check if today is a weekly reflection day
            for week_index, week_day in week_days.items():
                if days_since_start == week_day:
                    # Check if not yet completed
                    has_reflection = WeeklyReflection.objects.filter(
                        user=user,
                        cohort=cohort,
                        week_index=week_index
                    ).exists()
                    
                    if not has_reflection:
                        # TODO: Use proper email template
                        subject = f'Week {week_index} Reflection - {cohort.name}'
                        message = f'''
Hello {user.email},

It's time for your Week {week_index} reflection for the {cohort.name}.

Set your intention for this week: {settings.SITE_URL}/checkins/weekly/{cohort.id}/

Take your time. This is a moment for intentional reflection.

- Digital Minimalist Lab
'''
                        
                        send_mail(
                            subject,
                            message,
                            settings.DEFAULT_FROM_EMAIL,
                            [user.email],
                            fail_silently=False,
                        )
                        
                        sent_count += 1
                        break
        
        self.stdout.write(
            self.style.SUCCESS(f'Sent {sent_count} weekly reminders')
        )

