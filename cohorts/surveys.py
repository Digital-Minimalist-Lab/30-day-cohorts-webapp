from datetime import date
from typing import Dict, Any
from collections import defaultdict

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet
from django.db import transaction

from .models import Cohort, UserSurveyResponse
from surveys.models import SurveySubmission, Question, Survey, Answer

from surveys.forms import DynamicSurveyForm


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