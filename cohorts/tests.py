from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model

from .models import Cohort, TaskScheduler
from .services import (
    _get_once_task_due_dates,
    _get_daily_task_due_dates,
    _get_weekly_task_due_dates,
)
from surveys.models import Survey

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