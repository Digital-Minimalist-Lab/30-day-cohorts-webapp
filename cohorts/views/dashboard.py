from django.shortcuts import render, redirect
from django.http import HttpRequest, HttpResponse
from django.db.models import Count, Q
from cohorts.tasks import get_user_tasks, get_upcoming_tasks

from ..models import Cohort, Enrollment, UserSurveyResponse
from ..utils import get_user_today

import logging
logger = logging.getLogger(__name__)


def homepage(request: HttpRequest, next_cohort: Cohort | None = None) -> HttpResponse:
    """Redirect to dashboard if logged in, otherwise show homepage."""
    if next_cohort is None:
        next_cohort = next(iter(Cohort.objects.get_joinable()), None)
    context = {
        'cohort': next_cohort,
    }
    if next_cohort:
        context['seats_available'] = next_cohort.seats_available()
    return render(request, 'cohorts/homepage.html', context)

def dashboard(request: HttpRequest) -> HttpResponse:
    """Homepage showing today's tasks for logged-in users or enrollment landing for logged-out."""
    # Get next active cohort for enrollment landing
    next_cohort = next(iter(Cohort.objects.get_joinable()), None)

    # Get user's most recent enrollment (assuming one active cohort at a time)
    # Also fetch the total number of enrollments for the cohort in the same query.
    enrollment = None
    logger.info("User: %s", request.user if request.user else "None")
    if not request.user.is_anonymous:
        enrollment = Enrollment.objects.filter(
            user=request.user
        ).select_related('cohort').annotate(
            enrollment_count=Count('cohort__enrollments', filter=~Q(cohort__enrollments__status='pending'))
        ).order_by('-enrolled_at').first()
        

    if not request.user.is_authenticated or not enrollment or enrollment.status == 'pending':
        return homepage(request, next_cohort)
    
    cohort = enrollment.cohort
    today = get_user_today(request.user)
    tasks = get_user_tasks(request.user, cohort, today)
    upcoming_tasks = get_upcoming_tasks(cohort, today)

    submitted_scheduler_ids = set()
    if hasattr(request.user, 'profile') and request.user.profile.view_past_submissions:
        submitted_scheduler_ids = set(UserSurveyResponse.objects.filter(
            user=request.user,
            cohort=cohort,
            submission__isnull=False
        ).values_list('scheduler_id', flat=True))

    context = {
        'enrollment': enrollment,
        'cohort': cohort,
        'enrollment_count': enrollment.enrollment_count, # Use the annotated value
        'tasks': tasks,
        'upcoming_tasks': upcoming_tasks,
        'today': today,
        'submitted_scheduler_ids': submitted_scheduler_ids,
    }

    return render(request, 'cohorts/dashboard.html', context)
