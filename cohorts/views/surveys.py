from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.http import HttpRequest, HttpResponse
from django.contrib import messages
from typing import Any, Dict
from datetime import date
from django.views.generic.edit import FormView
from django.views.generic.list import ListView

from surveys.forms import DynamicSurveyForm
from surveys.models import Survey

from cohorts.models import Cohort, Enrollment, UserSurveyResponse, TaskScheduler
from cohorts.surveys import create_survey_submission
from cohorts.tasks import find_due_date

import logging
logger = logging.getLogger(__name__)


@method_decorator(login_required, name='dispatch')
class SurveyFormView(FormView):
    """
    A class-based view to handle displaying and processing a survey form.
    """
    form_class = DynamicSurveyForm

    def setup(self, request: HttpRequest, *args: Any, **kwargs: Any) -> None:
        """Initialize attributes for the view."""
        super().setup(request, *args, **kwargs)
        cohort_id = self.kwargs['cohort_id']
        scheduler_slug = self.kwargs['scheduler_slug']
        self.task_instance_id = self.kwargs['task_instance_id']

        self.cohort = get_object_or_404(Cohort, id=cohort_id)
        self.scheduler = get_object_or_404(TaskScheduler, cohort=self.cohort, slug=scheduler_slug)
        self.survey = self.scheduler.survey
        self.due_date = find_due_date(self.scheduler, self.task_instance_id)

    def get_template_names(self):
        """
        Return a list of template names to search for.
        Looks for a survey-specific template first, then a default.
        e.g., for an exit survey -> ['surveys/views/exit-survey_survey_form.html', 'surveys/views/default/survey_form.html']
        """
        return [
            f"surveys/views/{self.survey.slug.lower()}_survey_form.html",
            "surveys/views/default/survey_form.html",
        ]

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """
        Central entry point for the view. Handles validation and authorization.
        """
        # Verify enrollment
        if not Enrollment.objects.filter(user=request.user, cohort=self.cohort).exists():
            messages.error(request, "You are not enrolled in this cohort.")
            return redirect('cohorts:dashboard')

        # Check if already completed
        if UserSurveyResponse.objects.filter(
            user=request.user,
            cohort=self.cohort,
            scheduler=self.scheduler,
            task_instance_id=self.task_instance_id
        ).exists():
            messages.info(request, "You have already completed this survey.")
            return redirect('cohorts:dashboard')

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self) -> Dict[str, Any]:
        """Pass the survey object to the form's constructor."""
        kwargs = super().get_form_kwargs()
        kwargs['survey'] = self.survey
        return kwargs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add survey, cohort, and title information to the template context."""
        context = super().get_context_data(**kwargs)
        survey_context: dict[str, Any] = {
            'survey_name': self.survey.name,
            'cohort_name': self.cohort.name,
        }
        # add week_number and due_date to all contexts
        week_number = ((self.due_date - self.cohort.start_date).days // 7) + 1
        survey_context['week_number'] = week_number
        survey_context['due_date'] = self.due_date
        if self.survey.estimated_time_minutes:
          survey_context['estimated_time_minutes'] = self.survey.estimated_time_minutes

        context.update({
            'page_title': self.survey.title_template.format(**survey_context),
            'description': self.survey.description.format(**survey_context),
        })
        context.update(survey_context)
        return context

    def form_valid(self, form: DynamicSurveyForm) -> HttpResponse:
        """Process the valid form and create the survey submission."""
        create_survey_submission(
            user=self.request.user,
            cohort=self.cohort,
            scheduler=self.scheduler,
            survey=self.survey,
            form=form,
            task_instance_id=self.task_instance_id,
        )
        messages.success(self.request, f"'{self.survey.name}' completed successfully!")
        return redirect('cohorts:dashboard')


# Required for redirection to the checkout page.
class EntrySurveyOnboardingFormView(SurveyFormView):
    """A specialized view for the entry survey during onboarding that redirects to checkout."""

    def form_valid(self, form: DynamicSurveyForm) -> HttpResponse:
        """Process the valid form and redirect to checkout instead of dashboard."""
        create_survey_submission(
            user=self.request.user,
            cohort=self.cohort,
            scheduler=self.scheduler,
            survey=self.survey,
            form=form,
            task_instance_id=self.task_instance_id,
        )
        messages.success(self.request, f"'{self.survey.name}' completed successfully!")
        # Redirect to checkout instead of dashboard
        return redirect('cohorts:join_checkout')


@login_required
def survey_view(request: HttpRequest, cohort_id: int, scheduler_slug: str, task_instance_id: int) -> HttpResponse:
    """
    View to display and process a survey.
    This acts as a dispatcher to select the correct view class.
    """
    cohort = get_object_or_404(Cohort, id=cohort_id)
    scheduler = get_object_or_404(TaskScheduler, cohort=cohort, slug=scheduler_slug)
    logger.info(f"survey: {scheduler.survey}")
    return SurveyFormView.as_view()(request, cohort_id=cohort_id, scheduler_slug=scheduler_slug, task_instance_id=task_instance_id)


@login_required
def onboarding_survey_view(request: HttpRequest, cohort_id: int) -> HttpResponse:
    """
    View to display and process the onboarding survey.
    Uses cohort.onboarding_survey to find the survey and scheduler.
    Always uses task_instance_id=0 (first instance).
    """
    cohort = get_object_or_404(Cohort, id=cohort_id)

    if not cohort.onboarding_survey:
        messages.error(request, "No onboarding survey configured for this cohort.")
        return redirect('cohorts:join_checkout')

    scheduler = get_object_or_404(TaskScheduler, cohort=cohort, survey=cohort.onboarding_survey)
    logger.info(f"Onboarding survey: {scheduler.survey}")

    # Onboarding survey is always task_instance_id=0
    return EntrySurveyOnboardingFormView.as_view()(request, cohort_id=cohort_id, scheduler_slug=scheduler.slug, task_instance_id=0)


@method_decorator(login_required, name='dispatch')
class PastSurveysListView(ListView):
    """
    A view which can list survey results. 
    """
    template_name = "surveys/views/default/past_submissions_list.html"

    def setup(self, request: HttpRequest, *args: Any, **kwargs: Any) -> None:
        """Initialize the cohort and survey."""
        super().setup(request, *args, **kwargs)
        self.cohort = get_object_or_404(Cohort, id=self.kwargs['cohort_id'])
        self.survey = get_object_or_404(Survey, slug=self.kwargs['survey_slug'])

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Verify enrollment before proceeding."""
        if not Enrollment.objects.filter(user=request.user, cohort=self.cohort).exists():
            messages.error(request, 'You must be enrolled in this cohort.')
            return redirect('cohorts:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        """Return submissions for the user, cohort, and survey, with specific ordering."""
        return UserSurveyResponse.objects.filter(
            user=self.request.user,
            cohort=self.cohort,
            submission__survey=self.survey,
        ).select_related('submission').prefetch_related('submission__answers', 'submission__answers__question').order_by('-submission__completed_at')

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add dynamic page title, empty message, and summary template names."""
        context = super().get_context_data(**kwargs)

        # Dynamically generate summary template names to try.
        summary_template_names = [
            f"surveys/fragments/{self.survey.slug}_survey_summary.html",
            "surveys/fragments/default/survey_summary.html",
        ]

        logger.info(f"Using summary templates: {summary_template_names}")

        context.update({
            'page_title': f"Past {self.survey.name}s",
            'cohort': self.cohort,
            'summary_template_names': summary_template_names,
            'empty_message': f"No submissions for '{self.survey.name}' yet.",
        })
        return context




@method_decorator(login_required, name='dispatch')
class PastSubmissionsListView(ListView):
    """
    A view which can list survey results. 
    """
    template_name = "surveys/views/default/past_submissions_list.html"

    def setup(self, request: HttpRequest, *args: Any, **kwargs: Any) -> None:
        """Initialize the cohort and survey."""
        super().setup(request, *args, **kwargs)
        self.cohort = get_object_or_404(Cohort, id=self.kwargs['cohort_id'])
        self.scheduler = get_object_or_404(TaskScheduler, cohort=self.cohort, slug=self.kwargs['scheduler_slug'])

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Verify enrollment before proceeding."""
        if not Enrollment.objects.filter(user=request.user, cohort=self.cohort).exists():
            messages.error(request, 'You must be enrolled in this cohort.')
            return redirect('cohorts:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        """Return submissions for the user, cohort, and survey, with specific ordering."""
        return UserSurveyResponse.objects.filter(
            user=self.request.user,
            cohort=self.cohort,
            scheduler=self.scheduler,
        ).select_related('submission').prefetch_related('submission__answers', 'submission__answers__question').order_by('-submission__completed_at')

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add dynamic page title, empty message, and summary template names."""
        context = super().get_context_data(**kwargs)

        # Dynamically generate summary template names to try.
        summary_template_names = [
            f"surveys/fragments/{self.scheduler.survey.slug}_survey_summary.html",
            "surveys/fragments/default/survey_summary.html",
        ]

        logger.info(f"Using summary templates: {summary_template_names}")

        context.update({
            'page_title': f"Past {self.scheduler.survey.name}s",
            'cohort': self.cohort,
            'summary_template_names': summary_template_names,
            'empty_message': f"No submissions for '{self.scheduler.survey.name}' yet.",
        })
        return context
