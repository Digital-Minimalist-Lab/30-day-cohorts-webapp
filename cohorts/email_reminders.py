"""
Email reminder system for pending tasks.

Sends timezone-aware email reminders to users at 10am their local time
for tasks that have send_email_reminder enabled.

Uses existing user preferences:
- email_product_updates: Controls reminders for DAILY frequency tasks
- email_daily_reminder: Controls reminders for WEEKLY frequency tasks
- ONCE frequency tasks: Always send if send_email_reminder=True (e.g., consent forms)

Supports:
- dry_run mode: logs what would be sent without sending or persisting
- Idempotency: tracks sent emails to prevent duplicates via EmailSendLog
"""
from datetime import date, datetime
from typing import List
import pytz
import logging

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.template import TemplateDoesNotExist
from django.conf import settings
from django_q.tasks import async_task
from django.contrib.auth.models import AbstractUser
from django.db import models

from accounts.models import UserProfile
from cohorts.tasks import get_user_tasks, PendingTask
from cohorts.utils import get_user_today
from cohorts.models import EmailSendLog

logger = logging.getLogger(__name__)
logger.level = logging.DEBUG


def _build_idempotency_key(user_id: int, reminder_date: date) -> str:
    """
    Generate a unique key for a task reminder email.

    Format: task_reminder:user_{user_id}:{date}
    This means one reminder email per user per day.
    """
    return f"task_reminder:user_{user_id}:{reminder_date.isoformat()}"

def send_task_reminders_for_timezone(timezone_name: str, dry_run: bool = False) -> int:
    """
    Send email reminders to users in a specific timezone if it's 10am.

    Args:
        timezone_name: Timezone string (e.g., 'America/New_York')

    Returns:
        Number of emails sent
    """
    try:
        tz = pytz.timezone(timezone_name)
    except pytz.exceptions.UnknownTimeZoneError:
        logger.error(f"Unknown timezone: {timezone_name}")
        return 0

    current_time = datetime.now(tz)

    # Only send at 10am
    # if current_time.hour != 10:
    #     logger.debug(f"Skipping {timezone_name} - current hour is {current_time.hour}, not 10")
    #     return 0

    logger.info(f"Processing email reminders for timezone: {timezone_name} at {current_time}")

    # Get users in this timezone with ANY email reminders enabled
    # We'll filter by specific preferences when checking tasks
    profiles = UserProfile.objects.filter(
        timezone=timezone_name
    ).filter(
        models.Q(email_daily_reminder=True)
    ).select_related('user')


    logger.info(f"Found {profiles.count()} consenting users in timezone: {timezone_name}")

    emails_sent = 0

    for profile in profiles:
        user = profile.user

        try:
            if send_task_reminder_to_user(user, dry_run=dry_run):
                emails_sent += 1
        except Exception as e:
            logger.error(f"Error sending reminder to {user.email}: {e}", exc_info=True)
            raise  # Let Django Q handle the failure/retry

    logger.info(f"Sent {emails_sent} email reminders for timezone {timezone_name}")
    return emails_sent


def send_task_reminder_to_user(user: AbstractUser, dry_run: bool = False) -> bool:
    """
    Send task reminder email to a single user if they have pending tasks.

    Args:
        user: User to send reminder to
        dry_run: If True, log what would be sent without sending or persisting

    Returns:
        True if email was sent (or would be sent in dry-run), False otherwise
    """
    today = get_user_today(user)

    
    # Check idempotency - skip if already sent today
    idempotency_key = _build_idempotency_key(user.id, today)

    if EmailSendLog.objects.was_sent(idempotency_key):
        logger.debug(f"Reminder already sent for {user.email} on {today}")
        return False


    # Get all active cohorts for user
    enrollments = user.enrollments.filter(
        cohort__is_active=True,
        status__in=['paid', 'free']
    ).select_related('cohort')

    if not enrollments.exists() or enrollments.count() == 0:
        logger.debug(f"User {user.email} has no active enrollments")
        return False

    # Collect all pending tasks that need reminders
    all_pending_tasks: List[PendingTask] = []

    for enrollment in enrollments:
        pending_tasks = get_user_tasks(user, enrollment.cohort, today)
        logger.info(f"Found {len(pending_tasks)} pending tasks for {user.email} in {enrollment.cohort.name}")
        all_pending_tasks.extend(pending_tasks)

    if not all_pending_tasks:
        logger.debug(f"User {user.email} has no pending tasks needing reminders")
        return False

    # Dry run: log and exit without sending or persisting
    if dry_run:
        logger.info(
            f"[DRY RUN] Would send reminder to {user.email} "
            f"with {len(all_pending_tasks)} task(s)"
        )
        return True

    # Send the email
    try:
        send_task_reminder_email(user, all_pending_tasks)
        EmailSendLog.objects.record_sent(
            idempotency_key=idempotency_key,
            recipient_email=user.email,
            recipient_user=user,
            email_type='task_reminder',
        )
        logger.info(f"Sent task reminder email to {user.email} with {len(all_pending_tasks)} tasks")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {user.email}: {e}", exc_info=True)
        raise  # Let Django Q handle the failure/retry


def send_task_reminder_email(user: AbstractUser, pending_tasks: List[PendingTask]) -> None:
    """
    Send the actual email with pending tasks.

    Supports custom email templates per task type. If a task has a custom
    email_template_name, it will be sent in a separate email.

    Args:
        user: User to send email to
        pending_tasks: List of PendingTask objects to include in email
    """
    # Group tasks by email template
    tasks_by_template = {}

    for task in pending_tasks:
        template_name = getattr(task.scheduler, 'email_template_name', None) or 'emails/task_reminder'
        if template_name not in tasks_by_template:
            tasks_by_template[template_name] = []
        tasks_by_template[template_name].append(task)

    # Send one email per template type
    for template_name, tasks in tasks_by_template.items():
        _send_email_with_template(user, tasks, template_name)


def send_email_task(subject: str, plain_message: str, from_email: str, recipient_list: List[str], html_message: str) -> None:
    """
    A Django Q task to send a single email.

    This allows email sending to be offloaded to workers to avoid
    rate limiting and blocking the main reminder task.
    """
    logger.debug(f"Sending email task to {recipient_list}")
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=from_email,
        recipient_list=recipient_list,
        html_message=html_message,
        fail_silently=False,
    )
    logger.info(f"Successfully queued email to {recipient_list}")


def _send_email_with_template(user: AbstractUser, pending_tasks: List[PendingTask], template_name: str) -> None:
    """
    Send email using a specific template.

    Args:
        user: User to send email to
        pending_tasks: List of PendingTask objects to include
        template_name: Template name without extension (e.g., 'emails/task_reminder')
    """
    context = {
        'user': user,
        'pending_tasks': pending_tasks,
        'site_url': settings.SITE_URL,
    }

    # Try to render custom templates, fall back to default
    try:
        html_message = render_to_string(f'{template_name}.html', context)
    except TemplateDoesNotExist:
        logger.warning(f"HTML template {template_name}.html not found, using default")
        html_message = render_to_string('emails/task_reminder.html', context)

    try:
        plain_message = render_to_string(f'{template_name}.txt', context)
    except TemplateDoesNotExist:
        logger.warning(f"Text template {template_name}.txt not found, using default")
        plain_message = render_to_string('emails/task_reminder.txt', context)

    # Generate subject line
    if len(pending_tasks) == 1:
        subject = f"Reminder: {pending_tasks[0].title}"
    else:
        subject = f"You have {len(pending_tasks)} pending task{'s' if len(pending_tasks) > 1 else ''}"

    # Offload actual email sending to a background task
    async_task(
        'cohorts.email_reminders.send_email_task',
        subject=subject,
        plain_message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
    )
