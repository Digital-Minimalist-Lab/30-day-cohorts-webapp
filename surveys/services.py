from datetime import date
from django.contrib.auth.models import AbstractUser
from cohorts.models import Cohort
from surveys.models import Survey, SurveySubmission, Answer
from surveys.forms import DynamicSurveyForm


# Service functions
def create_survey_submission(
    *,
    user: AbstractUser,
    cohort: Cohort,
    survey: Survey,
    form: DynamicSurveyForm,
    due_date: date,
) -> SurveySubmission:
    """Creates a SurveySubmission and its related Answers from a validated form."""
    submission = SurveySubmission.objects.create(
        user=user,
        cohort=cohort,
        survey=survey,
        due_date=due_date,
    )

    for question in survey.questions.all():
        answer_value = form.cleaned_data.get(question.key)
        if answer_value is not None:
            Answer.objects.create(submission=submission, question=question, value=str(answer_value))
    return submission

