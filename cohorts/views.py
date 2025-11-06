from typing import Optional
from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AbstractUser
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.db.models import Q
import pytz
from .models import Cohort, Enrollment


def get_user_today(user: AbstractUser) -> date:
    """
    Get today's date in user's timezone.
    
    Args:
        user: Django User instance with associated UserProfile
        
    Returns:
        datetime.date: Today's date in user's timezone
    """
    from accounts.models import UserProfile
    
    # Get or create profile (defensive programming)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    user_tz = pytz.timezone(profile.timezone)
    return timezone.now().astimezone(user_tz).date()


def verify_enrollment(user: AbstractUser, cohort: Cohort) -> Optional[Enrollment]:
    """
    Verify that a user is enrolled in a cohort.
    
    This is a common pattern used across multiple views to ensure
    authorization before allowing access to cohort-specific resources.
    
    Args:
        user: Django User instance
        cohort: Cohort instance
        
    Returns:
        Enrollment instance if user is enrolled, None otherwise
    """
    return Enrollment.objects.filter(user=user, cohort=cohort).first()


def homepage(request: HttpRequest) -> HttpResponse:
    """Homepage showing today's tasks for logged-in users."""
    if not request.user.is_authenticated:
        return render(request, 'cohorts/landing.html')
    
    # Get user's most recent enrollment (assuming one active cohort at a time)
    enrollment = Enrollment.objects.filter(user=request.user).select_related('cohort').order_by('-enrolled_at').first()
    
    if not enrollment:
        # No enrollment, show cohort selection
        return redirect('cohorts:cohort_list')
    
    cohort = enrollment.cohort
    today = get_user_today(request.user)
    
    # Determine today's tasks
    tasks = []
    completed_tasks = []
    
    # Check entry survey
    entry_survey = enrollment.user.entry_surveys.filter(cohort=cohort).first()
    if not entry_survey:
        tasks.append({
            'type': 'entry_survey',
            'title': 'Complete Entry Survey',
            'description': 'Establish your baseline metrics',
            'url': f'/surveys/entry/{cohort.id}/',
        })
    else:
        completed_tasks.append({
            'type': 'entry_survey',
            'title': 'Entry Survey',
            'completed_at': entry_survey.completed_at,
            'url': f'/surveys/entry/{cohort.id}/',
        })
    
    # Check today's daily check-in
    daily_checkin = enrollment.user.daily_checkins.filter(cohort=cohort, date=today).first()
    if not daily_checkin:
        tasks.append({
            'type': 'daily_checkin',
            'title': 'Log Today\'s Check-In',
            'description': 'Complete your 5-step daily reflection',
            'url': f'/checkins/daily/{cohort.id}/',
        })
    else:
        completed_tasks.append({
            'type': 'daily_checkin',
            'title': f'Daily Check-In - {today}',
            'completed_at': daily_checkin.created_at,
            'url': f'/checkins/daily/{cohort.id}/',
        })
    
    # Check weekly reflection (days 7, 14, 21, 28)
    # With catch-up: Week 1 available days 7-13, Week 2 days 14-20, etc.
    days_since_start = (today - cohort.start_date).days
    week_days = {1: 7, 2: 14, 3: 21, 4: 28}
    
    for week_index, week_day in week_days.items():
        # Check if we're in the window for this week
        if days_since_start >= week_day and days_since_start < week_day + 7:
            weekly_reflection = enrollment.user.weekly_reflections.filter(
                cohort=cohort,
                week_index=week_index
            ).first()
            
            if not weekly_reflection:
                tasks.append({
                    'type': 'weekly_reflection',
                    'title': f'Set Week {week_index} Intention',
                    'description': f'Set your intention for week {week_index}',
                    'url': f'/checkins/weekly/{cohort.id}/',
                })
                break  # Only show the earliest incomplete reflection
            else:
                completed_tasks.append({
                    'type': 'weekly_reflection',
                    'title': f'Week {week_index} Reflection',
                    'completed_at': weekly_reflection.created_at,
                    'url': f'/checkins/weekly/{cohort.id}/',
                })
    
    # Check exit survey (if cohort ended)
    if today >= cohort.end_date:
        exit_survey = enrollment.user.exit_surveys.filter(cohort=cohort).first()
        if not exit_survey:
            tasks.append({
                'type': 'exit_survey',
                'title': 'Complete Exit Survey',
                'description': 'Reflect on your 30-day journey',
                'url': f'/surveys/exit/{cohort.id}/',
            })
        else:
            completed_tasks.append({
                'type': 'exit_survey',
                'title': 'Exit Survey',
                'completed_at': exit_survey.completed_at,
                'url': f'/surveys/exit/{cohort.id}/',
            })
    
    context = {
        'enrollment': enrollment,
        'cohort': cohort,
        'tasks': tasks,
        'completed_tasks': completed_tasks,
        'today': today,
    }
    
    return render(request, 'cohorts/homepage.html', context)


@login_required
def cohort_list(request: HttpRequest) -> HttpResponse:
    """List available cohorts."""
    today = timezone.now().date()
    
    # Get cohorts that can be joined (within 7 days of start and active)
    available_cohorts = Cohort.objects.filter(
        is_active=True
    ).filter(
        start_date__lte=today + timezone.timedelta(days=0),
        start_date__gte=today - timezone.timedelta(days=7)
    ).order_by('-start_date')
    
    # Get user's enrollments
    user_enrollments = Enrollment.objects.filter(user=request.user).values_list('cohort_id', flat=True)
    
    context = {
        'available_cohorts': available_cohorts,
        'user_enrollments': user_enrollments,
    }
    
    return render(request, 'cohorts/cohort_list.html', context)


@login_required
def cohort_join(request: HttpRequest, cohort_id: int) -> HttpResponse:
    """Join a cohort (with or without payment)."""
    cohort = get_object_or_404(Cohort, id=cohort_id)
    
    if not cohort.can_join():
        return render(request, 'cohorts/cohort_join_error.html', {
            'cohort': cohort,
            'message': 'This cohort is no longer accepting new members. You can join within 7 days of the start date.'
        })
    
    # Check if already enrolled
    enrollment, created = Enrollment.objects.get_or_create(
        user=request.user,
        cohort=cohort
    )
    
    if not created:
        return redirect('cohorts:homepage')
    
    # If payment is enabled, redirect to payment
    from django.conf import settings
    if settings.STRIPE_ENABLED and cohort.price_cents > 0:
        return redirect('payments:create_checkout', cohort_id=cohort.id)
    
    # Otherwise, redirect to entry survey
    return redirect('surveys:entry_survey', cohort_id=cohort.id)

