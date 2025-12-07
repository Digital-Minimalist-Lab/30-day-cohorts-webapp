from datetime import date, timedelta
from typing import List, Dict, Any
from dataclasses import dataclass, field
from collections import defaultdict

from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.db.models import QuerySet
from django.db import transaction
from django.urls import reverse

from cohorts.models import Cohort, TaskScheduler, UserSurveyResponse
from surveys.models import SurveySubmission, Question, Survey, Answer

from surveys.forms import DynamicSurveyForm

import logging
logger = logging.getLogger(__name__)


# Data-only classes
@dataclass
class PendingTask:
    """Represents a survey task that is due but not yet completed."""
    scheduler: TaskScheduler
    due_date: date
    title: str
    description: str
    url: str
    order: int = 0


def _get_once_task_due_dates(scheduler: TaskScheduler, cohort: Cohort, today: date) -> List[date]:
    """Generates due dates for a ONCE frequency scheduler."""
    if scheduler.offset_from == 'start':
        due_date = cohort.start_date + timedelta(days=scheduler.offset_days)
    else: # 'end'
        due_date = cohort.end_date + timedelta(days=scheduler.offset_days)
    
    if today >= due_date:
        return [due_date]
    return []


def _get_daily_task_due_dates(scheduler: TaskScheduler, cohort: Cohort, today: date) -> List[date]:
    """Generates due dates for a DAILY frequency scheduler."""
    if cohort.start_date <= today <= cohort.end_date:
        return [today]
    return []


def _get_weekly_task_due_dates(scheduler: TaskScheduler, cohort: Cohort, today: date) -> List[date]:
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



def get_user_tasks(user: AbstractUser, cohort: Cohort, today: date) -> (List[PendingTask], List[SurveySubmission]):
    """
    Generates the list of pending and completed tasks for a user in a cohort.

    Args:
        user: The user for whom to generate tasks.
        cohort: The cohort the user is enrolled in.
        today: The current date in the user's timezone.

    Returns:
        A tuple containing a list of PendingTask objects and a list of completed SurveySubmission objects.
    """
    pending_tasks = []
    schedulers = cohort.task_schedulers.select_related('survey').all()
    
    # Fetch all responses for the user and cohort at once.
    responses_qs = UserSurveyResponse.objects.filter(user=user, cohort=cohort).select_related('submission__survey')

    # Create a lookup set for (due_date, survey_id) for efficient checking.
    completed_task_keys = {(r.due_date, r.submission.survey_id) for r in responses_qs}
    completed_submissions = [r.submission for r in responses_qs]
    
    for scheduler in schedulers:
        frequency_config = TASK_FREQUENCY_HANDLERS.get(scheduler.frequency)
        if not frequency_config:
            continue

        handler = frequency_config['handler']
        order_func = frequency_config['order']
        
        due_dates = handler(scheduler, cohort, today)

        for due_date in due_dates:
            if (due_date, scheduler.survey_id) in completed_task_keys:
                continue

            # Note: week_number is only relevant for weekly tasks, but we can calculate it for context
            week_number = ((due_date - cohort.start_date).days // 7) + 1

            context = {'survey_name': scheduler.survey.name, 'due_date': due_date, 'week_number': week_number}
            title = (scheduler.task_title_template or scheduler.survey.title()).format(**context)
            description = (scheduler.task_description_template or scheduler.survey.description).format(**context)

            pending_tasks.append(PendingTask(
                scheduler=scheduler,
                due_date=due_date,
                title=title,
                description=description,
                url=reverse('cohorts:new_submission', kwargs={'cohort_id': cohort.id, 'survey_slug': scheduler.survey.slug, 'due_date': due_date.isoformat()}),
                order=order_func(scheduler)
            ))

    pending_tasks.sort(key=lambda x: (x.due_date, x.order))
    return pending_tasks, completed_submissions



def aggregate_checkin_data(submissions: QuerySet[SurveySubmission]) -> Dict[str, Any]:
    """
    Aggregates numerical data from a queryset of survey submissions.

    This function inspects the questions of the survey, identifies numerical
    metrics, and calculates statistics like average and change over time.

    Args:
        submissions: A QuerySet of SurveySubmission objects, ordered by completion date.

    Returns:
        A dictionary where keys are question keys and values are another dictionary containing 'avg', 'change', 'first', and 'last' stats.
    """
    if not submissions.exists():
        return {}

    # Identify which questions are numerical metrics from the survey definition.
    first_submission = submissions.first()
    if not first_submission or not first_submission.survey:
        return {}

    metric_questions = first_submission.survey.questions.filter(question_type=Question.QuestionType.INTEGER)
    metric_keys = {q.key for q in metric_questions}

    # Collect all values for each metric across all submissions.
    raw_values = defaultdict(list)
    for submission in submissions:
        for answer in submission.answers.all():
            if answer.question.key in metric_keys:
                try:
                    raw_values[answer.question.key].append(int(answer.value))
                except (ValueError, TypeError):
                    continue  # Skip non-integer or invalid values gracefully.

    # Calculate and structure the final aggregates.
    aggregates: Dict[str, Dict[str, Any]] = {}
    for key, values in raw_values.items():
        if not values:
            continue

        aggregates[key] = {
            'avg': sum(values) / len(values),
            'change': values[-1] - values[0] if len(values) > 1 else 0,
            'first': values[0],
            'last': values[-1],
        }

    return aggregates



# Service functions
def create_survey_submission(
    *,
    user: AbstractUser,
    cohort: Cohort,
    survey: Survey,
    form: DynamicSurveyForm,
    due_date: date,
) -> SurveySubmission:
    """
    Creates a SurveySubmission, its Answers, and a linking UserSurveyResponse
    from a validated form within a database transaction.
    """
    with transaction.atomic():
        # Create the core submission object
        submission = SurveySubmission.objects.create(
            survey=survey,
        )
        
        # Create the linking response object
        UserSurveyResponse.objects.create(
            user=user,
            cohort=cohort,
            submission=submission,
            due_date=due_date
        )
        
        # Create an Answer for each question in the form
        for question in survey.questions.all():
            answer_value = form.cleaned_data.get(question.key)
            if answer_value is not None:
                Answer.objects.create(submission=submission, question=question, value=str(answer_value))
                
    return submission
