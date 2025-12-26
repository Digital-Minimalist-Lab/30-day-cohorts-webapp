from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
import json

from .models import Cohort, TaskScheduler, UserSurveyResponse
from .tasks import (
    find_due_date,
    _get_once_task_instances,
    _get_daily_task_instances,
    _get_weekly_task_instances,
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

    def test_get_once_task_instances(self):
        """Test ONCE task instance generation. task_instance_id is always 0."""
        scheduler = TaskScheduler.objects.create(
            cohort=self.cohort,
            survey=self.survey,
            slug='once-task',
            frequency=TaskScheduler.Frequency.ONCE,
            offset_days=0,
            offset_from=TaskScheduler.OffsetFrom.COHORT_START,
        )

        # Before due date
        today = self.start_date - timedelta(days=1)
        self.assertEqual(_get_once_task_instances(scheduler, today), [])

        # On due date - task_instance_id is always 0 for ONCE
        today = self.start_date
        self.assertEqual(_get_once_task_instances(scheduler, today), [(0, self.start_date)])

        # After due date - still returns 0
        today = self.start_date + timedelta(days=1)
        self.assertEqual(_get_once_task_instances(scheduler, today), [(0, self.start_date)])

    def test_get_daily_task_instances_non_cumulative(self):
        """Test DAILY non-cumulative task instance generation. task_instance_id = day offset."""
        scheduler = TaskScheduler.objects.create(
            cohort=self.cohort,
            survey=self.survey,
            slug='daily-task',
            frequency=TaskScheduler.Frequency.DAILY,
            is_cumulative=False,
        )

        # Before cohort starts
        today = self.start_date - timedelta(days=1)
        self.assertEqual(_get_daily_task_instances(scheduler, today), [])

        # Day 0 (first day)
        today = self.start_date
        self.assertEqual(_get_daily_task_instances(scheduler, today), [(0, self.start_date)])

        # Day 5 - task_instance_id should be 5, not 0!
        today = self.start_date + timedelta(days=5)
        self.assertEqual(_get_daily_task_instances(scheduler, today), [(5, today)])

        # After cohort ends
        today = self.end_date + timedelta(days=1)
        self.assertEqual(_get_daily_task_instances(scheduler, today), [])

    def test_get_daily_task_instances_cumulative(self):
        """Test DAILY cumulative task instance generation."""
        scheduler = TaskScheduler.objects.create(
            cohort=self.cohort,
            survey=self.survey,
            slug='daily-cumulative',
            frequency=TaskScheduler.Frequency.DAILY,
            is_cumulative=True,
        )

        # Day 2 - should return all days from start
        today = self.start_date + timedelta(days=2)
        expected = [
            (0, self.start_date),
            (1, self.start_date + timedelta(days=1)),
            (2, self.start_date + timedelta(days=2)),
        ]
        self.assertEqual(_get_daily_task_instances(scheduler, today), expected)

    def test_get_weekly_task_instances_cumulative(self):
        """Test WEEKLY cumulative task instance generation. task_instance_id = week index."""
        scheduler = TaskScheduler.objects.create(
            cohort=self.cohort,
            survey=self.survey,
            slug='weekly-cumulative',
            frequency=TaskScheduler.Frequency.WEEKLY,
            day_of_week=0,  # Monday
            is_cumulative=True,
        )

        # In week 3 of the cohort (Tuesday)
        today = self.start_date + timedelta(days=15)

        # Should generate instances for weeks 0, 1, 2
        expected = [
            (0, self.start_date + timedelta(days=0)),   # Week 0 Monday
            (1, self.start_date + timedelta(days=7)),   # Week 1 Monday
            (2, self.start_date + timedelta(days=14)),  # Week 2 Monday
        ]
        self.assertEqual(_get_weekly_task_instances(scheduler, today), expected)

    def test_get_weekly_task_instances_non_cumulative(self):
        """Test WEEKLY non-cumulative task instance generation."""
        scheduler = TaskScheduler.objects.create(
            cohort=self.cohort,
            survey=self.survey,
            slug='weekly-non-cumulative',
            frequency=TaskScheduler.Frequency.WEEKLY,
            day_of_week=6,  # Sunday
            is_cumulative=False,
        )

        today = self.start_date + timedelta(days=15)  # Tuesday in week 3
        # Should only return week 1's Sunday (week_index=1) - the most recent past due
        week_2_sunday = self.start_date + timedelta(days=13)
        self.assertEqual(_get_weekly_task_instances(scheduler, today), [(1, week_2_sunday)])


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
            cohort=self.cohort, survey=self.entry_survey, slug="entry-survey-1",
            frequency=TaskScheduler.Frequency.ONCE,
            offset_days=0, offset_from=TaskScheduler.OffsetFrom.COHORT_START
        )
        TaskScheduler.objects.create(
            cohort=self.cohort, survey=self.daily_survey, slug="daily-check-in-1",
            frequency=TaskScheduler.Frequency.DAILY
        )
        TaskScheduler.objects.create(
            cohort=self.cohort, survey=self.weekly_survey, slug="weekly-reflection-1",
            frequency=TaskScheduler.Frequency.WEEKLY,
            day_of_week=6, is_cumulative=True # Sundays
        )

    def test_get_user_tasks_mid_cohort(self):
        """Test task generation mid-cohort with no tasks completed."""
        today = self.start_date + timedelta(days=8) # Tuesday of Week 2

        pending_tasks = get_user_tasks(self.user, self.cohort, today)

        self.assertEqual(len(pending_tasks), 3)

        # Expected tasks, sorted by due_date, then order
        # 1. Entry survey (due on day 0)
        self.assertEqual(pending_tasks[0].due_date, self.start_date)

        # 2. First weekly survey (due on Sunday of week 1)
        self.assertEqual(pending_tasks[1].due_date, self.start_date + timedelta(days=6))

        # 3. Daily survey for 'today'
        self.assertEqual(pending_tasks[2].due_date, today)

    def test_get_user_tasks_filters_completed_tasks(self):
        """Test that completed tasks are correctly filtered out."""
        today = self.start_date + timedelta(days=8) # Tuesday of Week 2

        # Get the entry scheduler
        entry_scheduler = TaskScheduler.objects.get(cohort=self.cohort, survey=self.entry_survey)

        # Simulate the user completing the entry survey (task_instance_id=0 for first instance)
        submission = SurveySubmission.objects.create(survey=self.entry_survey)
        UserSurveyResponse.objects.create(
            user=self.user,
            cohort=self.cohort,
            scheduler=entry_scheduler,
            submission=submission,
            task_instance_id=0,
        )

        pending_tasks = get_user_tasks(self.user, self.cohort, today)

        # The entry survey should now be filtered out from pending_tasks.
        self.assertEqual(len(pending_tasks), 2)

        # Check that the pending tasks are the weekly and daily ones.
        pending_due_dates = {task.due_date for task in pending_tasks}
        self.assertNotIn(self.start_date, pending_due_dates)

        # Verify the URL is correctly generated with task_instance_id
        daily_task = next(t for t in pending_tasks if t.due_date == today)
        # Day 8 of cohort means task_instance_id=8 for daily tasks
        day_offset = (today - self.start_date).days
        expected_url = reverse('cohorts:new_submission', kwargs={
            'cohort_id': self.cohort.id,
            'scheduler_slug': 'daily-check-in-1',
            'task_instance_id': day_offset
        })
        self.assertEqual(daily_task.url, expected_url)

    def test_get_user_tasks_filters_completed_daily_task(self):
        """Test that a completed recurring (daily) task is filtered out."""
        today = self.start_date + timedelta(days=2)  # Day 2 of cohort

        # Get the daily scheduler
        daily_scheduler = TaskScheduler.objects.get(cohort=self.cohort, survey=self.daily_survey)

        # Simulate the user completing the daily check-in for 'today'
        # task_instance_id = day offset = 2 for day 2
        day_offset = (today - self.start_date).days
        submission = SurveySubmission.objects.create(survey=self.daily_survey)
        UserSurveyResponse.objects.create(
            user=self.user,
            cohort=self.cohort,
            scheduler=daily_scheduler,
            submission=submission,
            task_instance_id=day_offset,
        )

        pending_tasks = get_user_tasks(self.user, self.cohort, today)

        # The daily survey should now be filtered out from pending_tasks.
        pending_due_dates = {task.due_date for task in pending_tasks}
        self.assertNotIn(today, pending_due_dates)

        # The entry survey should still be pending.
        self.assertIn(self.start_date, pending_due_dates)
        self.assertEqual(len(pending_tasks), 1)
        self.assertEqual(pending_tasks[0].due_date, self.start_date)