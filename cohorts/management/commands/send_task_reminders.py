"""
Management command to send task reminder emails.

This command should be run hourly (e.g., via cron or django-q2 scheduler).
It checks each timezone and sends reminders to users at 10am their local time.

Usage:
    python manage.py send_task_reminders
    
    # Or with verbosity
    python manage.py send_task_reminders --verbosity 2
"""
from typing import Any
from django.core.management.base import BaseCommand

from accounts.models import UserProfile
from cohorts.email_reminders import send_task_reminders_for_timezone


class Command(BaseCommand):
    help = 'Send email reminders for pending tasks (run hourly)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--timezone',
            type=str,
            help='Only process a specific timezone (for testing)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without sending emails',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Send task reminders to users at 10am their local time."""
        verbosity = options.get('verbosity', 1)
        specific_timezone = options.get('timezone')
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No emails will be sent'))
        
        # Get all unique timezones from users with reminders enabled
        if specific_timezone:
            timezones = [specific_timezone]
            if verbosity >= 1:
                self.stdout.write(f"Processing specific timezone: {specific_timezone}")
        else:
            timezones = UserProfile.objects.values_list('timezone', flat=True).distinct()
            
            if verbosity >= 1:
                self.stdout.write(f"Found {len(timezones)} unique timezones to process")
        
        total_emails_sent = 0
        
        for tz in timezones:
            try:
                # Actually send emails
                emails_sent = send_task_reminders_for_timezone(tz, dry_run=dry_run)
                total_emails_sent += emails_sent
                
                if emails_sent > 0:
                    self.stdout.write(
                        self.style.SUCCESS(f"  ✓ Sent {emails_sent} email(s) for timezone: {tz}")
                    )
                elif verbosity >= 2:
                    self.stdout.write(f"  - No emails sent for timezone: {tz}")
                    
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"  ✗ Error processing timezone {tz}: {e}")
                )
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN COMPLETE - No emails were sent'))
        else:
            if total_emails_sent > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'\n✓ Successfully sent {total_emails_sent} task reminder email(s)')
                )
            else:
                if verbosity >= 1:
                    self.stdout.write(
                        self.style.WARNING('No emails sent (no users at 10am in their timezone)')
                    )

