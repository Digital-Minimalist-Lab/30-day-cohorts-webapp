from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.http import HttpRequest, HttpResponse
from django.contrib import messages
from typing import Any, Dict
from datetime import date
from django.views.generic.edit import FormView
from django.views.generic.list import ListView
from cohorts.models import Cohort, Enrollment 
from .services import create_survey_submission
from .forms import DynamicSurveyForm
from .models import Survey, SurveySubmission

import logging
logger = logging.getLogger(__name__)


@method_decorator(login_required, name='dispatch')
class SurveyTaskView(FormView):
    """
    A class-based view to handle displaying and processing a survey task.
    This replaces the `survey_view` function and the `SurveyViewType` registry.
    """
    form_class = DynamicSurveyForm
    template_name = "surveys/survey_form.html"

    def setup(self, request: HttpRequest, *args: Any, **kwargs: Any) -> None:
        """Initialize attributes for the view."""
        super().setup(request, *args, **kwargs)
        cohort_id = self.kwargs['cohort_id']
        survey_slug = self.kwargs['survey_slug']
        self.cohort = get_object_or_404(Cohort, id=cohort_id)
        self.survey = get_object_or_404(Survey, slug=survey_slug)
        try:
            self.due_date = date.fromisoformat(self.kwargs['due_date'])
        except (ValueError, TypeError, KeyError):
            self.due_date = None

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """
        Central entry point for the view. Handles validation and authorization.
        """
        # Verify enrollment
        if not Enrollment.objects.filter(user=request.user, cohort=self.cohort).exists():
            messages.error(request, "You are not enrolled in this cohort.")
            return redirect('cohorts:cohort_list')

        # Validate due_date
        if not self.due_date:
            messages.error(request, "A valid due date is required to perform this task.")
            return redirect('cohorts:homepage')

        # Check if already completed
        if SurveySubmission.objects.filter(user=request.user, cohort=self.cohort, survey=self.survey, due_date=self.due_date).exists():
            messages.info(request, "You have already completed this task.")
            return redirect('cohorts:homepage')

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self) -> Dict[str, Any]:
        """Pass the survey object to the form's constructor."""
        kwargs = super().get_form_kwargs()
        kwargs['survey'] = self.survey
        return kwargs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add survey, cohort, and title information to the template context."""
        context = super().get_context_data(**kwargs)
        
        # Attempt to find the scheduler to get templates and frequency context
        task_title_template = self.survey.name

        week_number = ((self.due_date - self.cohort.start_date).days // 7) + 1
        title_context = {'survey_name': self.survey.name, 'due_date': self.due_date, 'week_number': week_number}
        page_title = (task_title_template).format(**title_context)

        context.update({
            'survey': self.survey,
            'cohort': self.cohort,
            'page_title': page_title,
            'due_date': self.due_date,
            'week_number': week_number,
        })
        return context

    def form_valid(self, form: DynamicSurveyForm) -> HttpResponse:
        """Process the valid form and create the survey submission."""
        create_survey_submission(
            user=self.request.user,
            cohort=self.cohort,
            survey=self.survey,
            form=form,
            due_date=self.due_date,
        )
        messages.success(self.request, f"'{self.survey.name}' completed successfully!")
        return redirect('cohorts:homepage')


class ExitSurveyFormView(SurveyTaskView):
    """A specialized view for the exit survey that shows baseline answers."""
    template_name = "survey_views/exit_survey_form.html"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['entry_survey_answers'] = self._get_entry_survey_answers()
        return context

    def _get_entry_survey_answers(self) -> Dict[str, str]:
        """Helper to fetch answers from the user's entry survey for a given cohort."""
        try:
            entry_submission = SurveySubmission.objects.filter(
                user=self.request.user,
                cohort=self.cohort,
                survey__purpose=Survey.Purpose.ENTRY,
            ).prefetch_related('answers', 'answers__question').order_by('completed_at').first()
            if entry_submission:
                return {answer.question.key: answer.value for answer in entry_submission.answers.all()}
        except (Survey.DoesNotExist):
            logger.warning(f"No entry survey found for cohort {self.cohort.id} when trying to get entry answers.")
        return {}


@login_required
def survey_view(request: HttpRequest, cohort_id: int, survey_slug: str, due_date: str) -> HttpResponse:
    """
    View to display and process a survey.
    This acts as a dispatcher to select the correct view class.
    """
    survey = get_object_or_404(Survey, slug=survey_slug)
    if survey.purpose == Survey.Purpose.EXIT:
        view_class = ExitSurveyFormView
    else:
        view_class = SurveyTaskView
    return view_class.as_view()(request, cohort_id=cohort_id, survey_slug=survey_slug, due_date=due_date)


@method_decorator(login_required, name='dispatch')
class PastSubmissionsListView(ListView):
    """
    A generic base view to list past survey submissions for a given survey.
    """
    template_name = "surveys/past_submissions_list.html"
    page_title: str
    summary_template_path: str = "surveys/generic_summary.html"
    empty_message: str

    def setup(self, request: HttpRequest, *args: Any, **kwargs: Any) -> None:
        """Initialize the cohort."""
        super().setup(request, *args, **kwargs)
        self.cohort = get_object_or_404(Cohort, id=self.kwargs['cohort_id'])
        self.survey = get_object_or_404(Survey, slug=self.kwargs['survey_slug'])

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Verify enrollment before proceeding."""
        if not Enrollment.objects.filter(user=request.user, cohort=self.cohort).exists():
            messages.error(request, 'You must be enrolled in this cohort.')
            return redirect('cohorts:cohort_list')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        """Return the submissions for the user, cohort, and survey"""
        return SurveySubmission.objects.filter(
            user=self.request.user,
            survey=self.survey,
            cohort=self.cohort,
        ).prefetch_related('answers', 'answers__question')

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        # Dynamically create a page title if not explicitly set.
        page_title = self.page_title if hasattr(self, 'page_title') else f"Past {self.survey.name}s"
        empty_message = self.empty_message if hasattr(self, 'empty_message') else f"No submissions for '{self.survey.name}' yet."

        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': page_title,
            'cohort': self.cohort,
            'summary_template_path': self.summary_template_path,
            'empty_message': empty_message,
        })
        return context



class PastCheckinsView(PastSubmissionsListView):
    page_title = "Past Check-Ins"
    summary_template_path = "survey_views/checkin_summary.html"
    empty_message = "No check-ins yet."
    ordering = ['-completed_at']

class PastReflectionsView(PastSubmissionsListView):
    page_title = "Past Weekly Reflections"
    summary_template_path = "survey_views/reflection_summary.html"
    empty_message = "No reflections yet."
    ordering = ['completed_at']

@login_required
def past_submission_view(request: HttpRequest, cohort_id: int, survey_slug: str) -> HttpResponse:
    """
    View to display and process a survey.
    This acts as a dispatcher to select the correct view class.
    """
    survey = get_object_or_404(Survey, slug=survey_slug)
    if survey.purpose == Survey.Purpose.DAILY_CHECKIN:
        view_class = PastCheckinsView
    elif survey.purpose == Survey.Purpose.WEEKLY_REFLECTION: 
        view_class = PastReflectionsView
    else:
        view_class = PastSubmissionsListView
    return view_class.as_view()(request, cohort_id=cohort_id, survey_slug=survey_slug)
