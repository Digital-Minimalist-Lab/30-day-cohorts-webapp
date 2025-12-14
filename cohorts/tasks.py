from datetime import date, timedelta
from typing import List
from dataclasses import dataclass

from django.contrib.auth.models import AbstractUser
from django.urls import reverse

from .models import Cohort, TaskScheduler, UserSurveyResponse

import logging
logger = logging.getLogger(__name__)


# Data-only classes
@dataclass
class PendingTask:
    """Represents a survey task that is due but not yet completed."""
    scheduler: TaskScheduler
    user: AbstractUser
    due_date: date
    title: str
    description: str
    url: str
    order: int = 0


def _get_once_task_due_dates(scheduler: TaskScheduler, today: date) -> List[date]:
    """Generates due dates for a ONCE frequency scheduler."""
    if scheduler.offset_from == 'start':
        due_date = scheduler.cohort.start_date + timedelta(days=scheduler.offset_days)
    else: # 'end'
        due_date = scheduler.cohort.end_date + timedelta(days=scheduler.offset_days)
    
    if today >= due_date:
        return [due_date]
    return []


def _get_daily_task_due_dates(scheduler: TaskScheduler, today: date) -> List[date]:
    """Generates due dates for a DAILY frequency scheduler."""
    if scheduler.cohort.start_date <= today <= scheduler.cohort.end_date:
        return [today]
    return []


def _get_weekly_task_due_dates(scheduler: TaskScheduler, today: date) -> List[date]:
    cohort = scheduler.cohort
    """Generates due dates for a WEEKLY frequency scheduler."""
    due_dates = []

    # Our convention is now Monday=0, ..., Sunday=6, which matches Python's weekday().
    target_weekday = scheduler.day_of_week

    days_until_first_due_date = (target_weekday - cohort.start_date.weekday() + 7) % 7
    first_due_date = cohort.start_date + timedelta(days=days_until_first_due_date)

    # Dynamically calculate the number of weeks based on cohort duration
    total_days = (cohort.end_date - cohort.start_date).days
    num_weeks = (total_days // 7) + 1

    for i in range(num_weeks):
        due_date = first_due_date + timedelta(weeks=i)
        if cohort.start_date <= due_date <= cohort.end_date and today >= due_date:
            due_dates.append(due_date)

    if not scheduler.is_cumulative and due_dates:
        return [max(due_dates)] # Only the most recent past due date
    
    return due_dates


TASK_FREQUENCY_HANDLERS = {
    TaskScheduler.Frequency.ONCE: {
        'handler': _get_once_task_due_dates,
        'order': lambda s: 1 if s.offset_from == 'start' else 4
    },
    TaskScheduler.Frequency.DAILY: {
        'handler': _get_daily_task_due_dates,
        'order': lambda s: 2
    },
    TaskScheduler.Frequency.WEEKLY: {
        'handler': _get_weekly_task_due_dates,
        'order': lambda s: 3
    },
}



def get_user_tasks(user: AbstractUser, cohort: Cohort, today: date) -> List[PendingTask]:
    """
    Generates the list of pending and completed tasks for a user in a cohort.
    """
    pending_tasks = []
    schedulers = TaskScheduler.objects.filter(cohort=cohort).select_related('survey').all()
    
    # Fetch all responses for the user and cohort at once.
    responses_qs = UserSurveyResponse.objects.filter(user=user, cohort=cohort).select_related('submission__survey')

    # Create a lookup set for (due_date, survey_id) for efficient checking.
    completed_task_keys = {(r.due_date, r.submission.survey_id) for r in responses_qs}
    
    for scheduler in schedulers:
        frequency_config = TASK_FREQUENCY_HANDLERS.get(scheduler.frequency)
        if not frequency_config:
            continue

        handler = frequency_config['handler']
        order_func = frequency_config['order']
        
        due_dates = handler(scheduler, today)

        for due_date in due_dates:
            if (due_date, scheduler.survey_id) in completed_task_keys:
                continue

            week_number = ((due_date - scheduler.cohort.start_date).days // 7) + 1
            context = {'survey_name': scheduler.survey.name, 'due_date': due_date, 'week_number': week_number}
            title = (scheduler.task_title_template or scheduler.survey.title()).format(**context)
            description = (scheduler.task_description_template or scheduler.survey.description).format(**context)

            pending_tasks.append(PendingTask(
                scheduler=scheduler,
                user=user,
                due_date=due_date,
                title=title,
                description=description,
                url=reverse('cohorts:new_submission', kwargs={'cohort_id': scheduler.cohort.id, 'survey_slug': scheduler.survey.slug, 'due_date': due_date.isoformat()}),
                order=order_func(scheduler)
            ))

    pending_tasks.sort(key=lambda x: (x.due_date, x.order))
    return pending_tasks