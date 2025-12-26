from django.contrib.auth.models import AbstractUser
from django.db import transaction

from .models import Cohort, UserSurveyResponse, TaskScheduler
from surveys.models import SurveySubmission, Survey, Answer

from surveys.forms import DynamicSurveyForm


def create_survey_submission(
    *,
    user: AbstractUser,
    cohort: Cohort,
    scheduler: TaskScheduler,
    survey: Survey,
    form: DynamicSurveyForm,
    task_instance_id: int,
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
            scheduler=scheduler,
            submission=submission,
            task_instance_id=task_instance_id,
        )

        # Create an Answer for each question in the form
        for question in survey.questions.all():
            answer_value = form.cleaned_data.get(question.key)
            if answer_value is not None:
                Answer.objects.create(submission=submission, question=question, value=str(answer_value))

    return submission