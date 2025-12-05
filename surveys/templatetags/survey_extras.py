from django import template
from surveys.models import SurveySubmission
register = template.Library()

@register.filter
def answer_by_key(submission: SurveySubmission, key: str):
    """
    Given a SurveySubmission, find the value of the answer corresponding to the given question key.
    This is efficient if `answers` and `answers__question` have been prefetched.
    """
    if not submission:
        return ""
    for answer in submission.answers.all():
        if answer.question.key == key:
            return answer.value
    return ""
