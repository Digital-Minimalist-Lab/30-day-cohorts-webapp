from datetime import date, timedelta
from typing import List, Tuple
from dataclasses import dataclass

from django.contrib.auth.models import AbstractUser
from django.urls import reverse

from .models import Cohort, TaskScheduler, UserSurveyResponse

import logging
logger = logging.getLogger(__name__)


# Type alias for task instances: (task_instance_id, due_date)
TaskInstance = Tuple[int, date]


# Data-only classes
@dataclass
class PendingTask:
    """Represents a survey task that is due but not yet completed."""
    user: AbstractUser
    scheduler_slug: str
    task_instance_id: int
    due_date: date
    title: str
    description: str
    url: str
    order: int = 0
    estimated_time_minutes: int | None = None


@dataclass
class UpcomingTask:
    """Represents an upcoming task type that will occur in the future."""
    title: str
    frequency: str  # 'Daily', 'Weekly', or a specific date for ONCE
    next_date: date
    day_of_week: str | None = None  # For weekly tasks, e.g., 'Mondays'
    estimated_time_minutes: int | None = None


def find_due_date(scheduler: TaskScheduler, task_instance_id: int) -> date:
    """
    Calculates the due date for a given task instance.

    For ONCE: due_date = reference_date + offset_days (task_instance_id is always 0)
    For DAILY: due_date = cohort.start_date + task_instance_id days
    For WEEKLY: due_date = first_weekly_due_date + task_instance_id weeks
    """
    cohort = scheduler.cohort

    if scheduler.frequency == TaskScheduler.Frequency.ONCE:
        ref_date = None
        if scheduler.offset_from == TaskScheduler.OffsetFrom.ENROLL_START:
            ref_date = cohort.enrollment_start_date
        elif scheduler.offset_from == TaskScheduler.OffsetFrom.ENROLL_END:
            ref_date = cohort.enrollment_end_date
        elif scheduler.offset_from == TaskScheduler.OffsetFrom.COHORT_START:
            ref_date = cohort.start_date
        elif scheduler.offset_from == TaskScheduler.OffsetFrom.COHORT_END:
            ref_date = cohort.end_date

        if not ref_date:
            raise ValueError(f"Invalid offset_from: {scheduler.offset_from}")

        return ref_date + timedelta(days=scheduler.offset_days or 0)

    elif scheduler.frequency == TaskScheduler.Frequency.DAILY:
        return cohort.start_date + timedelta(days=task_instance_id)

    elif scheduler.frequency == TaskScheduler.Frequency.WEEKLY:
        target_weekday = scheduler.day_of_week
        days_until_first = (target_weekday - cohort.start_date.weekday() + 7) % 7
        first_due_date = cohort.start_date + timedelta(days=days_until_first)
        return first_due_date + timedelta(weeks=task_instance_id)

    else:
        raise ValueError(f"Unsupported frequency: {scheduler.frequency}")


def _get_once_task_instances(scheduler: TaskScheduler, today: date) -> List[TaskInstance]:
    """
    Generates task instances for a ONCE frequency scheduler.
    task_instance_id is always 0 for ONCE tasks.
    """
    try:
        due_date = find_due_date(scheduler, 0)
    except ValueError:
        return []

    if today >= due_date:
        return [(0, due_date)]
    return []


def _get_daily_task_instances(scheduler: TaskScheduler, today: date) -> List[TaskInstance]:
    """
    Generates task instances for a DAILY frequency scheduler.
    task_instance_id = day offset from cohort start (0-indexed).
    """
    cohort = scheduler.cohort
    if not (cohort.start_date <= today <= cohort.end_date):
        return []

    if scheduler.is_cumulative:
        # Return all days from start to today
        num_days = (today - cohort.start_date).days + 1
        return [(i, find_due_date(scheduler, i)) for i in range(num_days)]
    else:
        # Non-cumulative: only today's task
        task_id = (today - cohort.start_date).days
        return [(task_id, find_due_date(scheduler, task_id))]


def _get_weekly_task_instances(scheduler: TaskScheduler, today: date) -> List[TaskInstance]:
    """
    Generates task instances for a WEEKLY frequency scheduler.
    task_instance_id = week index (0-indexed).
    """
    cohort = scheduler.cohort
    instances = []

    # Calculate max possible weeks
    total_days = (cohort.end_date - cohort.start_date).days
    num_weeks = (total_days // 7) + 1

    for week_index in range(num_weeks):
        due_date = find_due_date(scheduler, week_index)
        if cohort.start_date <= due_date <= cohort.end_date and today >= due_date:
            instances.append((week_index, due_date))

    if not scheduler.is_cumulative and instances:
        return [instances[-1]]  # Only the most recent (highest week_index)

    return instances


TASK_FREQUENCY_HANDLERS = {
    TaskScheduler.Frequency.ONCE: {
        'handler': _get_once_task_instances,
        'order': lambda s: 1 if s.offset_from == TaskScheduler.OffsetFrom.COHORT_START else 4
    },
    TaskScheduler.Frequency.DAILY: {
        'handler': _get_daily_task_instances,
        'order': lambda s: 2
    },
    TaskScheduler.Frequency.WEEKLY: {
        'handler': _get_weekly_task_instances,
        'order': lambda s: 3
    },
}


def get_user_tasks(user: AbstractUser, cohort: Cohort, today: date) -> List[PendingTask]:
    """
    Generates the list of pending tasks for a user in a cohort.
    """
    pending_tasks = []
    schedulers = TaskScheduler.objects.filter(cohort=cohort).select_related('survey').all()

    # Fetch all responses for the user and cohort at once.
    responses_qs = UserSurveyResponse.objects.filter(user=user, cohort=cohort).select_related('scheduler')

    # Create a lookup set of completed (scheduler_slug, task_instance_id) tuples for efficient checking.
    completed_task_keys = {(r.scheduler.slug, r.task_instance_id) for r in responses_qs}

    for scheduler in schedulers:
        frequency_config = TASK_FREQUENCY_HANDLERS.get(scheduler.frequency)
        if not frequency_config:
            continue

        handler = frequency_config['handler']
        order_func = frequency_config['order']

        # Handlers now return List[(task_instance_id, due_date)]
        task_instances = handler(scheduler, today)

        for task_instance_id, due_date in task_instances:
            if (scheduler.slug, task_instance_id) in completed_task_keys:
                continue

            week_number = ((due_date - scheduler.cohort.start_date).days // 7) + 1
            context = {
                'survey_name': scheduler.survey.name,
                'due_date': due_date,
                'week_number': week_number,
                'estimated_time_minutes': scheduler.survey.estimated_time_minutes,
            }
            title = (scheduler.task_title_template or scheduler.survey.title()).format(**context)
            description = (scheduler.task_description_template or scheduler.survey.description).format(**context)

            pending_tasks.append(PendingTask(
                user=user,
                scheduler_slug=scheduler.slug,
                task_instance_id=task_instance_id,
                due_date=due_date,
                title=title,
                description=description,
                url=reverse('cohorts:new_submission', kwargs={
                    'cohort_id': scheduler.cohort.id,
                    'scheduler_slug': scheduler.slug,
                    'task_instance_id': task_instance_id
                }),
                order=order_func(scheduler),
                estimated_time_minutes=scheduler.survey.estimated_time_minutes,
            ))

    pending_tasks.sort(key=lambda x: (x.due_date, x.order))
    return pending_tasks


DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def get_upcoming_tasks(cohort: Cohort, today: date) -> List[UpcomingTask]:
    """
    Returns a list of upcoming task types that haven't started yet.
    For recurring tasks, shows the task once with its frequency.
    """
    upcoming_tasks = []
    schedulers = TaskScheduler.objects.filter(cohort=cohort).select_related('survey').all()

    for scheduler in schedulers:
        title = scheduler.task_title_template or scheduler.survey.title()
        # Remove template placeholders for the preview
        title = title.replace('{survey_name}', scheduler.survey.name)
        title = title.replace('{week_number}', '')
        title = title.replace('{due_date}', '')
        title = title.strip()

        estimated_time = scheduler.survey.estimated_time_minutes

        if scheduler.frequency == TaskScheduler.Frequency.ONCE:
            try:
                due_date = find_due_date(scheduler, 0)
            except ValueError:
                continue
            # Only show if it's in the future
            if due_date > today:
                upcoming_tasks.append(UpcomingTask(
                    title=title,
                    frequency=due_date.strftime('%b %d'),
                    next_date=due_date,
                    estimated_time_minutes=estimated_time,
                ))

        elif scheduler.frequency == TaskScheduler.Frequency.DAILY:
            # Daily tasks start when the cohort starts
            if cohort.start_date > today:
                upcoming_tasks.append(UpcomingTask(
                    title=title,
                    frequency=f"Daily, starting {cohort.start_date.strftime('%b %d')}",
                    next_date=cohort.start_date,
                    estimated_time_minutes=estimated_time,
                ))

        elif scheduler.frequency == TaskScheduler.Frequency.WEEKLY:
            # Find the first occurrence
            first_due = find_due_date(scheduler, 0)
            if first_due > today:
                day_name = DAY_NAMES[scheduler.day_of_week] + 's' if scheduler.day_of_week is not None else None
                upcoming_tasks.append(UpcomingTask(
                    title=title,
                    frequency='Weekly',
                    next_date=first_due,
                    day_of_week=day_name,
                    estimated_time_minutes=estimated_time,
                ))

    upcoming_tasks.sort(key=lambda x: x.next_date)
    return upcoming_tasks