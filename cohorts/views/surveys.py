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

from cohorts.models import Cohort, Enrollment, UserSurveyResponse
from cohorts.surveys import create_survey_submission

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
        survey_slug = self.kwargs['survey_slug']
        self.cohort = get_object_or_404(Cohort, id=cohort_id)
        self.survey = get_object_or_404(Survey, slug=survey_slug)
        try:
            self.due_date = date.fromisoformat(self.kwargs['due_date'])
        except (ValueError, TypeError, KeyError):
            self.due_date = None

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

        # Validate due_date
        if not self.due_date:
            messages.error(request, "A valid due date is required to perform this survey.")
            return redirect('cohorts:dashboard')

        # Check if already completed
        if UserSurveyResponse.objects.filter(user=request.user, cohort=self.cohort, submission__survey=self.survey, due_date=self.due_date).exists():
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
        if self.due_date:
            week_number = ((self.due_date - self.cohort.start_date).days // 7) + 1
            survey_context.update({
                'due_date': self.due_date.isoformat(),
                'week_number': week_number,
            })
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
            survey=self.survey,
            form=form,
            due_date=self.due_date,
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
            survey=self.survey,
            form=form,
            due_date=self.due_date,
        )
        messages.success(self.request, f"'{self.survey.name}' completed successfully!")
        # Redirect to checkout instead of dashboard
        return redirect('cohorts:join_checkout')


@login_required
def survey_view(request: HttpRequest, cohort_id: int, survey_slug: str, due_date: str) -> HttpResponse:
    """
    View to display and process a survey.
    This acts as a dispatcher to select the correct view class.
    """
    survey = get_object_or_404(Survey, slug=survey_slug)
    logger.info(f"survey: {survey}")
    return SurveyFormView.as_view()(request, cohort_id=cohort_id, survey_slug=survey_slug, due_date=due_date)


@login_required
def onboarding_survey_view(request: HttpRequest, cohort_id: int, survey_slug: str, due_date: str) -> HttpResponse:
    """
    View to display and process a survey during onboarding.
    This uses the EntrySurveyOnboardingFormView which redirects to checkout after completion.
    """
    survey = get_object_or_404(Survey, slug=survey_slug)
    logger.info(f"Onboarding survey: {survey}")
    # Use the onboarding view that redirects to checkout
    return EntrySurveyOnboardingFormView.as_view()(request, cohort_id=cohort_id, survey_slug=survey_slug, due_date=due_date)


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
