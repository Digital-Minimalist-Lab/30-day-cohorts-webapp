from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
import json

from .models import Cohort, TaskScheduler, UserSurveyResponse
from .tasks import (
    _get_once_task_due_dates,
    _get_daily_task_due_dates,
    _get_weekly_task_due_dates,
    get_user_tasks,
)
from surveys.models import Survey, SurveySubmission

User = get_user_model()


class TaskGenerationServiceTests(TestCase):

    def setUp(self):
        """Set up a cohort and survey for testing."""
        self.start_date = date(2025, 9, 1) # this was a Monday
        self.end_date = self.start_date + timedelta(days=29)
        self.cohort = Cohort.objects.create(
            name="Test Cohort",
            start_date=self.start_date,
            end_date=self.end_date,
        )
        self.survey = Survey.objects.create(name="Test Survey", slug="test-survey")

    def test_get_once_task_due_dates(self):
        """Test ONCE task due date generation."""
        scheduler = TaskScheduler.objects.create(
            cohort=self.cohort,
            survey=self.survey,
            frequency=TaskScheduler.Frequency.ONCE,
            offset_days=0,
            offset_from=TaskScheduler.OffsetFrom.START,
        )

        # Before due date
        today = self.start_date - timedelta(days=1)
        self.assertEqual(_get_once_task_due_dates(scheduler, self.cohort, today), [])

        # On due date
        today = self.start_date
        self.assertEqual(_get_once_task_due_dates(scheduler, self.cohort, today), [self.start_date])

        # After due date
        today = self.start_date + timedelta(days=1)
        self.assertEqual(_get_once_task_due_dates(scheduler, self.cohort, today), [self.start_date])

    def test_get_daily_task_due_dates(self):
        """Test DAILY task due date generation."""
        scheduler = TaskScheduler.objects.create(
            cohort=self.cohort,
            survey=self.survey,
            frequency=TaskScheduler.Frequency.DAILY,
        )
        
        # Before cohort starts
        today = self.start_date - timedelta(days=1)
        self.assertEqual(_get_daily_task_due_dates(scheduler, self.cohort, today), [])

        # During cohort
        today = self.start_date + timedelta(days=5)
        self.assertEqual(_get_daily_task_due_dates(scheduler, self.cohort, today), [today])

        # After cohort ends
        today = self.end_date + timedelta(days=1)
        self.assertEqual(_get_daily_task_due_dates(scheduler, self.cohort, today), [])

    def test_get_weekly_task_due_dates_cumulative(self):
        """Test WEEKLY cumulative task due date generation."""
        scheduler = TaskScheduler.objects.create(
            cohort=self.cohort,
            survey=self.survey,
            frequency=TaskScheduler.Frequency.WEEKLY,
            day_of_week=0,  # Monday
            is_cumulative=True,
        )

        # In week 3 of the cohort
        today = self.start_date + timedelta(days=15) # A Tuesday in week 3
        
        # Should generate due dates for the Mondays of week 1, 2, and 3.
        expected_dates = [
            self.start_date + timedelta(days=0),  # Week 1 Monday
            self.start_date + timedelta(days=7),  # Week 2 Monday
            self.start_date + timedelta(days=14), # Week 3 Monday
        ]
        self.assertEqual(_get_weekly_task_due_dates(scheduler, self.cohort, today), expected_dates)

    def test_get_weekly_task_due_dates_non_cumulative(self):
        """Test WEEKLY non-cumulative task due date generation."""
        scheduler = TaskScheduler.objects.create(
            cohort=self.cohort,
            survey=self.survey,
            frequency=TaskScheduler.Frequency.WEEKLY,
            day_of_week=6,  # Sunday
            is_cumulative=False,
        )

        today = self.start_date + timedelta(days=15) # A Tuesday in week 3
        # Should only generate the most recent past due date
        expected_dates = [self.start_date + timedelta(days=13)] # Week 2 Sunday
        self.assertEqual(_get_weekly_task_due_dates(scheduler, self.cohort, today), expected_dates)


class GetUserTasksServiceTests(TestCase):

    def setUp(self):
        """Set up a user, cohort, surveys, and schedulers for integration testing."""
        self.user = User.objects.create_user(email="test@example.com", password="password", username="testuser")
        self.start_date = date(2025, 9, 1) # A Monday
        self.end_date = self.start_date + timedelta(days=29)
        self.cohort = Cohort.objects.create(
            name="Integration Test Cohort",
            start_date=self.start_date,
            end_date=self.end_date,
        )

        # Create surveys
        self.entry_survey = Survey.objects.create(name="Entry Survey", slug="entry-survey-1")
        self.daily_survey = Survey.objects.create(name="Daily Check-in", slug="daily-check-in-1")
        self.weekly_survey = Survey.objects.create(name="Weekly Reflection", slug="weekly-reflection-1")

        # Create schedulers
        TaskScheduler.objects.create(
            cohort=self.cohort, survey=self.entry_survey, frequency=TaskScheduler.Frequency.ONCE,
            offset_days=0, offset_from=TaskScheduler.OffsetFrom.START
        )
        TaskScheduler.objects.create(
            cohort=self.cohort, survey=self.daily_survey, frequency=TaskScheduler.Frequency.DAILY
        )
        TaskScheduler.objects.create(
            cohort=self.cohort, survey=self.weekly_survey, frequency=TaskScheduler.Frequency.WEEKLY,
            day_of_week=6, is_cumulative=True # Sundays
        )

    def test_get_user_tasks_mid_cohort(self):
        """Test task generation mid-cohort with no tasks completed."""
        today = self.start_date + timedelta(days=8) # Tuesday of Week 2

        pending_tasks, completed_submissions = get_user_tasks(self.user, self.cohort, today)

        self.assertEqual(len(pending_tasks), 3)
        self.assertEqual(len(completed_submissions), 0)

        # Expected tasks, sorted by due_date, then order
        # 1. Entry survey (due on day 0)
        self.assertEqual(pending_tasks[0].scheduler.survey, self.entry_survey)
        self.assertEqual(pending_tasks[0].due_date, self.start_date)

        # 2. First weekly survey (due on Sunday of week 1)
        self.assertEqual(pending_tasks[1].scheduler.survey, self.weekly_survey)
        self.assertEqual(pending_tasks[1].due_date, self.start_date + timedelta(days=6))

        # 3. Daily survey for 'today'
        self.assertEqual(pending_tasks[2].scheduler.survey, self.daily_survey)
        self.assertEqual(pending_tasks[2].due_date, today)

    def test_get_user_tasks_filters_completed_tasks(self):
        """Test that completed tasks are correctly filtered out."""
        today = self.start_date + timedelta(days=8) # Tuesday of Week 2

        # Simulate the user completing the entry survey on its due date.
        entry_due_date = self.start_date
        submission = SurveySubmission.objects.create(survey=self.entry_survey)
        UserSurveyResponse.objects.create(
            user=self.user,
            cohort=self.cohort,
            submission=submission,
            due_date=entry_due_date
        )

        pending_tasks, completed_submissions = get_user_tasks(self.user, self.cohort, today)

        # The entry survey should now be in completed_submissions, not pending_tasks.
        self.assertEqual(len(pending_tasks), 2)
        self.assertEqual(len(completed_submissions), 1)
        self.assertEqual(completed_submissions[0], submission)

        # Check that the pending tasks are the weekly and daily ones.
        pending_surveys = {task.scheduler.survey for task in pending_tasks}
        self.assertNotIn(self.entry_survey, pending_surveys)
        self.assertIn(self.weekly_survey, pending_surveys)
        self.assertIn(self.daily_survey, pending_surveys)

        # Verify the URL is correctly generated
        daily_task = next(t for t in pending_tasks if t.scheduler.survey == self.daily_survey)
        expected_url = reverse('cohorts:new_submission', kwargs={'cohort_id': self.cohort.id, 'survey_slug': 'daily-check-in', 'due_date': today.isoformat()})
        self.assertEqual(daily_task.url, expected_url)

    def test_get_user_tasks_filters_completed_daily_task(self):
        """Test that a completed recurring (daily) task is filtered out."""
        today = self.start_date + timedelta(days=2) # Wednesday of Week 1

        # Simulate the user completing the daily check-in for 'today'.
        submission = SurveySubmission.objects.create(survey=self.daily_survey)
        UserSurveyResponse.objects.create(
            user=self.user,
            cohort=self.cohort,
            submission=submission,
            due_date=today
        )

        pending_tasks, completed_submissions = get_user_tasks(self.user, self.cohort, today)

        # The daily survey should now be in completed_submissions, not pending_tasks.
        self.assertEqual(len(completed_submissions), 1)

        pending_surveys = {task.scheduler.survey for task in pending_tasks}
        self.assertNotIn(self.daily_survey, pending_surveys)

        # The entry survey should still be pending.
        self.assertIn(self.entry_survey, pending_surveys)
        self.assertEqual(len(pending_tasks), 1, f"Found pending tasks: {json.dumps(pending_tasks)}")
        self.assertEqual(pending_tasks[0].scheduler.survey, self.entry_survey)