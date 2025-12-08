from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from django.db.models import Count
from cohorts.tasks import get_user_tasks

from ..models import Cohort, Enrollment
from ..utils import get_user_today

# This is a temporary landing page which exists until the rest of the application is ready.
# That should be _fine_. There is now way this will go wrong.
def landing(request: HttpRequest) -> HttpResponse:
    context = None
    return render(request, 'landing/index.html', context)


def homepage(request: HttpRequest) -> HttpResponse:
    """Homepage showing today's tasks for logged-in users or enrollment landing for logged-out."""
    if not request.user.is_authenticated:
        # Get next active cohort for enrollment landing
        next_cohort = Cohort.objects.get_upcoming().first()
        
        context = {
            'cohort': next_cohort,
        }
        if next_cohort:
            context['seats_available'] = next_cohort.seats_available()
        return render(request, 'cohorts/landing.html', context)
    
    # Get user's most recent enrollment (assuming one active cohort at a time)
    # Also fetch the total number of enrollments for the cohort in the same query.
    enrollment = Enrollment.objects.filter(
        user=request.user
    ).select_related('cohort').annotate(
        enrollment_count=Count('cohort__enrollments')
    ).order_by('-enrolled_at').first()
    
    
    if not enrollment or enrollment.status == 'pending':
        # No enrollment, show signup prompt
        return render(request, 'cohorts/homepage.html', {
            'no_enrollment': True,
            'available_cohort': Cohort.objects.get_upcoming().first(),
        })
    
    cohort = enrollment.cohort
    today = get_user_today(request.user)
    tasks, completed_tasks = get_user_tasks(request.user, cohort, today)
    
    context = {
        'enrollment': enrollment,
        'cohort': cohort,
        'enrollment_count': enrollment.enrollment_count, # Use the annotated value
        'tasks': tasks,
        'completed_tasks': completed_tasks,
        'today': today,
    }
    
    return render(request, 'cohorts/homepage.html', context)

