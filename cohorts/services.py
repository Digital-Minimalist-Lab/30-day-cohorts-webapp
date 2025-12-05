from datetime import date, timedelta
from typing import List, Dict, Any
from dataclasses import dataclass, field
from collections import defaultdict

from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.db.models import QuerySet
from django.urls import reverse

from cohorts.models import Cohort, TaskScheduler
from surveys.models import SurveySubmission, Question

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
    submissions_qs = SurveySubmission.objects.filter(user=user, cohort=cohort)

    # Create a lookup set for (due_date, survey_id) for efficient checking.
    completed_task_keys = {(s.due_date, s.survey_id) for s in submissions_qs}
    completed_submissions = list(submissions_qs.select_related('survey'))
    
    for scheduler in schedulers:
        if scheduler.frequency == TaskScheduler.Frequency.ONCE:
            due_date = cohort.start_date + timedelta(days=scheduler.offset_days) if scheduler.offset_from == 'start' else cohort.end_date + timedelta(days=scheduler.offset_days)
            
            if today >= due_date:
                is_completed = (due_date, scheduler.survey_id) in completed_task_keys
                if not is_completed:
                    context = {'survey_name': scheduler.survey.name, 'due_date': due_date}
                    title = (scheduler.task_title_template or scheduler.survey.title()).format(**context)
                    description = (scheduler.task_description_template or scheduler.survey.description).format(**context)

                    pending_tasks.append(PendingTask(
                        scheduler=scheduler,
                        due_date=due_date,
                        title=title,
                        description=description,
                        url=reverse('surveys:new_submission', kwargs={'cohort_id': cohort.id, 'survey_slug': scheduler.survey.slug, 'due_date': due_date.isoformat()}),
                        order=1 if scheduler.offset_from == 'start' else 4
                    ))

        elif scheduler.frequency == TaskScheduler.Frequency.DAILY:
            if cohort.start_date <= today <= cohort.end_date: # Only show daily check-ins during the cohort
                is_completed = (today, scheduler.survey_id) in completed_task_keys
                if not is_completed:
                    context = {'survey_name': scheduler.survey.name, 'due_date': today}
                    title = (scheduler.task_title_template or scheduler.survey.name).format(**context)
                    description = (scheduler.task_description_template or scheduler.survey.description).format(**context)

                    pending_tasks.append(PendingTask(
                        scheduler=scheduler,
                        due_date=today,
                        title=title,
                        description=description,
                        url=reverse('surveys:new_submission', kwargs={'cohort_id': cohort.id, 'survey_slug': scheduler.survey.slug, 'due_date': today.isoformat()}),
                        order=2
                    ))

        elif scheduler.frequency == TaskScheduler.Frequency.WEEKLY:

            for week_num in range(1, 5): # Assuming a 4-week cohort
                week_start_day = (week_num - 1) * 7
                due_date = cohort.start_date + timedelta(days=week_start_day + scheduler.day_of_week)

                if today >= due_date:
                    is_completed = (due_date, scheduler.survey_id) in completed_task_keys

                    if not is_completed:
                        context = {'survey_name': scheduler.survey.name, 'due_date': due_date, 'week_number': week_num}
                        title = (scheduler.task_title_template or f"Week {{week_number}}: {{survey_name}}").format(**context)
                        description = (scheduler.task_description_template or scheduler.survey.description).format(**context)

                        task = PendingTask(
                            scheduler=scheduler,
                            due_date=due_date,
                            title=title,
                            description=description,
                            url=reverse('surveys:new_submission', kwargs={'cohort_id': cohort.id, 'survey_slug': scheduler.survey.slug, 'due_date': due_date.isoformat()}),
                            order=3
                        )
                        pending_tasks.append(task)
                        if not scheduler.is_cumulative:
                            break # Only show the most recent if not cumulative

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
