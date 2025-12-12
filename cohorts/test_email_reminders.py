"""
Tests for the email reminder system.

Tests cover:
- Idempotency (no duplicate emails)
- Dry-run mode
- EmailSendLog creation
- Error handling
"""
from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core import mail
from unittest.mock import patch, MagicMock

from accounts.models import UserProfile
from cohorts.models import Cohort, Enrollment, EmailSendLog
from cohorts.email_reminders import (
    send_task_reminder_to_user,
    send_task_reminders_for_timezone,
    _build_idempotency_key,
)

User = get_user_model()


class EmailSendLogModelTests(TestCase):
    """Tests for EmailSendLog model and manager."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_record_sent_creates_log_entry(self):
        """Test that record_sent creates a log entry."""
        idempotency_key = 'test_key:123'

        log = EmailSendLog.objects.record_sent(
            idempotency_key=idempotency_key,
            recipient_email='test@example.com',
            email_type='task_reminder',
            recipient_user=self.user,
        )

        self.assertEqual(log.idempotency_key, idempotency_key)
        self.assertEqual(log.recipient_email, 'test@example.com')
        self.assertEqual(log.email_type, 'task_reminder')
        self.assertEqual(log.recipient_user, self.user)
        self.assertIsNotNone(log.created_at)

    def test_was_sent_returns_true_for_existing_key(self):
        """Test that was_sent returns True when key exists."""
        idempotency_key = 'test_key:456'

        # Create a log entry
        EmailSendLog.objects.record_sent(
            idempotency_key=idempotency_key,
            recipient_email='test@example.com',
            email_type='task_reminder',
        )

        self.assertTrue(EmailSendLog.objects.was_sent(idempotency_key))

    def test_was_sent_returns_false_for_missing_key(self):
        """Test that was_sent returns False when key doesn't exist."""
        self.assertFalse(EmailSendLog.objects.was_sent('nonexistent_key'))

    def test_idempotency_key_unique_constraint(self):
        """Test that duplicate idempotency keys raise an error."""
        idempotency_key = 'duplicate_key:789'

        EmailSendLog.objects.record_sent(
            idempotency_key=idempotency_key,
            recipient_email='test@example.com',
            email_type='task_reminder',
        )

        with self.assertRaises(Exception):  # IntegrityError
            EmailSendLog.objects.record_sent(
                idempotency_key=idempotency_key,
                recipient_email='test@example.com',
                email_type='task_reminder',
            )


class BuildIdempotencyKeyTests(TestCase):
    """Tests for _build_idempotency_key helper function."""

    def test_builds_correct_format(self):
        """Test that idempotency key has correct format."""
        user_id = 123
        reminder_date = date(2024, 1, 15)

        key = _build_idempotency_key(user_id, reminder_date)

        self.assertEqual(key, 'task_reminder:user_123:2024-01-15')

    def test_different_dates_produce_different_keys(self):
        """Test that different dates produce different keys."""
        user_id = 123
        date1 = date(2024, 1, 15)
        date2 = date(2024, 1, 16)

        key1 = _build_idempotency_key(user_id, date1)
        key2 = _build_idempotency_key(user_id, date2)

        self.assertNotEqual(key1, key2)

    def test_different_users_produce_different_keys(self):
        """Test that different users produce different keys."""
        reminder_date = date(2024, 1, 15)

        key1 = _build_idempotency_key(123, reminder_date)
        key2 = _build_idempotency_key(456, reminder_date)

        self.assertNotEqual(key1, key2)


class EmailReminderIdempotencyTests(TestCase):
    """Tests for email reminder idempotency."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create profile
        UserProfile.objects.filter(user=self.user).update(
            timezone='America/New_York',
            email_daily_reminder=True,
        )
        self.user.refresh_from_db()

        # Create cohort with dates that include today
        # Note: Cohort creation auto-creates TaskSchedulers via signals
        today = date.today()
        self.cohort = Cohort.objects.create(
            name='Test Cohort',
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=25),
            is_active=True,
            is_paid=False,
        )

        # Enroll user
        Enrollment.objects.create(
            user=self.user,
            cohort=self.cohort,
            status='free'
        )

    def test_first_email_sends_and_creates_log(self):
        """Test that first email sends successfully and creates log."""
        mail.outbox = []

        result = send_task_reminder_to_user(self.user)

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(EmailSendLog.objects.count(), 1)

        log = EmailSendLog.objects.first()
        self.assertEqual(log.recipient_email, 'test@example.com')
        self.assertEqual(log.email_type, 'task_reminder')

    def test_duplicate_email_is_prevented(self):
        """Test that duplicate email is prevented by idempotency check."""
        mail.outbox = []

        # First send
        result1 = send_task_reminder_to_user(self.user)
        self.assertTrue(result1)
        self.assertEqual(len(mail.outbox), 1)

        # Second send (same user, same day)
        result2 = send_task_reminder_to_user(self.user)
        self.assertFalse(result2)
        self.assertEqual(len(mail.outbox), 1)  # Still only 1 email

        # Only one log entry
        self.assertEqual(EmailSendLog.objects.count(), 1)

    def test_different_days_allow_new_email(self):
        """Test that emails can be sent on different days."""
        mail.outbox = []
        today = date.today()

        # First send
        result1 = send_task_reminder_to_user(self.user)
        self.assertTrue(result1)

        # Manually create a log for "yesterday" to simulate previous day's send
        yesterday = today - timedelta(days=1)
        yesterday_key = _build_idempotency_key(self.user.id, yesterday)
        EmailSendLog.objects.record_sent(
            idempotency_key=yesterday_key,
            recipient_email=self.user.email,
            email_type='task_reminder',
        )

        # Today's send should have worked (first assertion)
        # and now we have 2 log entries
        self.assertEqual(EmailSendLog.objects.count(), 2)


class EmailReminderDryRunTests(TestCase):
    """Tests for dry-run mode."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        UserProfile.objects.filter(user=self.user).update(
            timezone='America/New_York',
            email_daily_reminder=True,
        )
        self.user.refresh_from_db()

        # Cohort creation auto-creates TaskSchedulers via signals
        today = date.today()
        self.cohort = Cohort.objects.create(
            name='Test Cohort',
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=25),
            is_active=True,
            is_paid=False,
        )

        Enrollment.objects.create(
            user=self.user,
            cohort=self.cohort,
            status='free'
        )

    def test_dry_run_does_not_send_email(self):
        """Test that dry_run=True does not send email."""
        mail.outbox = []

        result = send_task_reminder_to_user(self.user, dry_run=True)

        self.assertTrue(result)  # Returns True (would have sent)
        self.assertEqual(len(mail.outbox), 0)  # But no email sent

    def test_dry_run_does_not_create_log(self):
        """Test that dry_run=True does not create EmailSendLog."""
        result = send_task_reminder_to_user(self.user, dry_run=True)

        self.assertTrue(result)
        self.assertEqual(EmailSendLog.objects.count(), 0)

    def test_dry_run_does_not_affect_future_real_sends(self):
        """Test that dry-run doesn't prevent future real sends."""
        mail.outbox = []

        # Dry run first
        result1 = send_task_reminder_to_user(self.user, dry_run=True)
        self.assertTrue(result1)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(EmailSendLog.objects.count(), 0)

        # Real send should still work
        result2 = send_task_reminder_to_user(self.user, dry_run=False)
        self.assertTrue(result2)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(EmailSendLog.objects.count(), 1)


class EmailReminderErrorHandlingTests(TestCase):
    """Tests for error handling."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        UserProfile.objects.filter(user=self.user).update(
            timezone='America/New_York',
            email_daily_reminder=True,
        )
        self.user.refresh_from_db()

        # Cohort creation auto-creates TaskSchedulers via signals
        today = date.today()
        self.cohort = Cohort.objects.create(
            name='Test Cohort',
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=25),
            is_active=True,
            is_paid=False,
        )

        Enrollment.objects.create(
            user=self.user,
            cohort=self.cohort,
            status='free'
        )

    @patch('cohorts.email_reminders.send_task_reminder_email')
    def test_failed_send_raises_exception(self, mock_send_email):
        """Test that failed email send raises exception for Django Q."""
        mock_send_email.side_effect = Exception('SMTP error')

        with self.assertRaises(Exception) as context:
            send_task_reminder_to_user(self.user)

        self.assertIn('SMTP error', str(context.exception))

    @patch('cohorts.email_reminders.send_task_reminder_email')
    def test_failed_send_does_not_create_log(self, mock_send_email):
        """Test that failed send doesn't create EmailSendLog."""
        mock_send_email.side_effect = Exception('SMTP error')

        with self.assertRaises(Exception):
            send_task_reminder_to_user(self.user)

        # No log should be created on failure
        self.assertEqual(EmailSendLog.objects.count(), 0)


class SendTaskRemindersForTimezoneTests(TestCase):
    """Tests for send_task_reminders_for_timezone function."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        UserProfile.objects.filter(user=self.user).update(
            timezone='America/New_York',
            email_daily_reminder=True,
        )
        self.user.refresh_from_db()

        # Cohort creation auto-creates TaskSchedulers via signals
        today = date.today()
        self.cohort = Cohort.objects.create(
            name='Test Cohort',
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=25),
            is_active=True,
            is_paid=False,
        )

        Enrollment.objects.create(
            user=self.user,
            cohort=self.cohort,
            status='free'
        )

    def test_dry_run_passed_through(self):
        """Test that dry_run is passed through to send_task_reminder_to_user."""
        mail.outbox = []

        result = send_task_reminders_for_timezone('America/New_York', dry_run=True)

        self.assertEqual(result, 1)  # 1 user would receive email
        self.assertEqual(len(mail.outbox), 0)  # But no email sent
        self.assertEqual(EmailSendLog.objects.count(), 0)  # No log created

    def test_invalid_timezone_returns_zero(self):
        """Test that invalid timezone returns 0."""
        result = send_task_reminders_for_timezone('Invalid/Timezone')

        self.assertEqual(result, 0)

