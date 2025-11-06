from typing import Any
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from cohorts.models import Enrollment
from checkins.models import DailyCheckin
import pytz


class Command(BaseCommand):
    help = 'Send daily check-in reminders to opted-in users'

    def handle(self, *args: Any, **options: Any) -> None:
        """Send email reminders for daily check-ins."""
        sent_count = 0
        
        # Get all active enrollments with users who opted in
        enrollments = Enrollment.objects.filter(
            user__profile__email_daily_reminder=True,
            cohort__is_active=True
        ).select_related('user', 'user__profile', 'cohort')
        
        for enrollment in enrollments:
            user = enrollment.user
            cohort = enrollment.cohort
            
            # Get user's today (defensive - get or create profile)
            from accounts.models import UserProfile
            profile, _ = UserProfile.objects.get_or_create(user=user)
            user_tz = pytz.timezone(profile.timezone)
            today = timezone.now().astimezone(user_tz).date()
            
            # Check if already completed today
            has_checkin = DailyCheckin.objects.filter(
                user=user,
                cohort=cohort,
                date=today
            ).exists()
            
            if not has_checkin:
                # TODO: Use proper email template
                subject = f'Daily Check-In Reminder - {cohort.name}'
                message = f'''
Hello {user.email},

This is your daily reminder to complete your check-in for the {cohort.name}.

Complete your check-in here: {settings.SITE_URL}/checkins/daily/{cohort.id}/

This is a calm reminder, not a notification. Complete it when you're ready.

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
        
        self.stdout.write(
            self.style.SUCCESS(f'Sent {sent_count} daily reminders')
        )

