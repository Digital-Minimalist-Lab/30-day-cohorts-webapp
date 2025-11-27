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
from allauth.account.forms import LoginForm, SignupForm


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


# This is a temporary landing page which exists until the rest of the application is ready.
# That should be _fine_. There is now way this will go wrong.
def landing(request: HttpRequest) -> HttpResponse:
    context = None
    return render(request, 'landing/index.html', context)


def homepage(request: HttpRequest) -> HttpResponse:
    """Homepage showing today's tasks for logged-in users or enrollment landing for logged-out."""
    if not request.user.is_authenticated:
        # Get next active cohort for enrollment landing
        today = timezone.now().date()
        next_cohort = Cohort.objects.filter(
            is_active=True,
            start_date__gte=today
        ).order_by('start_date').first()
        
        context = {
            'cohort': next_cohort,
        }
        if next_cohort:
            context['seats_available'] = next_cohort.seats_available()
        
        return render(request, 'cohorts/landing.html', context)
    
    # Get user's most recent enrollment (assuming one active cohort at a time)
    enrollment = Enrollment.objects.filter(user=request.user).select_related('cohort').order_by('-enrolled_at').first()
    
    if not enrollment or enrollment.status == 'pending':
        # No enrollment, show signup prompt
        context = {
            'no_enrollment': True,
            'available_cohorts': Cohort.objects.filter(is_active=True).order_by('start_date').first(),
        }
        return render(request, 'cohorts/homepage.html', context)
    
    cohort = enrollment.cohort
    today = get_user_today(request.user)
    
    # Get enrollment count
    enrollment_count = cohort.enrollments.count()
    
    # Determine today's tasks in chronological order
    tasks = []
    completed_tasks = []
    
    # 1. Check entry survey (always first)
    entry_survey = enrollment.user.entry_surveys.filter(cohort=cohort).first()
    if not entry_survey:
        tasks.append({
            'type': 'entry_survey',
            'title': 'Complete Entry Survey',
            'description': 'Establish your baseline metrics',
            'url': f'/surveys/entry/{cohort.id}/',
            'order': 1,
        })
    else:
        completed_tasks.append({
            'type': 'entry_survey',
            'title': 'Entry Survey',
            'completed_at': entry_survey.completed_at,
            'url': f'/surveys/entry/{cohort.id}/',
        })
    
    # 2. Check today's daily check-in
    daily_checkin = enrollment.user.daily_checkins.filter(cohort=cohort, date=today).first()
    if not daily_checkin:
        tasks.append({
            'type': 'daily_checkin',
            'title': 'Log Today\'s Check-In',
            'description': 'Complete your 5-step daily reflection',
            'url': f'/checkins/daily/{cohort.id}/',
            'order': 2,
        })
    else:
        completed_tasks.append({
            'type': 'daily_checkin',
            'title': f'Daily Check-In - {today}',
            'completed_at': daily_checkin.created_at,
            'url': f'/checkins/daily/{cohort.id}/',
        })
    
    # 3. Check weekly reflection (days 7, 14, 21, 28)
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
                    'order': 3,
                })
                break  # Only show the earliest incomplete reflection
            else:
                completed_tasks.append({
                    'type': 'weekly_reflection',
                    'title': f'Week {week_index} Reflection',
                    'completed_at': weekly_reflection.created_at,
                    'url': f'/checkins/weekly/{cohort.id}/',
                })
    
    # 4. Check exit survey (if cohort ended)
    if today >= cohort.end_date:
        exit_survey = enrollment.user.exit_surveys.filter(cohort=cohort).first()
        if not exit_survey:
            tasks.append({
                'type': 'exit_survey',
                'title': 'Complete Exit Survey',
                'description': 'Reflect on your 30-day journey',
                'url': f'/surveys/exit/{cohort.id}/',
                'order': 4,
            })
        else:
            completed_tasks.append({
                'type': 'exit_survey',
                'title': 'Exit Survey',
                'completed_at': exit_survey.completed_at,
                'url': f'/surveys/exit/{cohort.id}/',
            })
    
    # Sort tasks by order
    tasks.sort(key=lambda x: x['order'])
    
    context = {
        'enrollment': enrollment,
        'cohort': cohort,
        'tasks': tasks,
        'completed_tasks': completed_tasks,
        'today': today,
        'enrollment_count': enrollment_count,
        'no_enrollment': False,
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
    user_enrollments = Enrollment.objects.filter(Q(user=request.user) & ~Q(status='pending')).values_list('cohort_id', flat=True)
    
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
    
    if enrollment.status != 'pending':
        return redirect('cohorts:homepage')
    
    # If payment is enabled, redirect to payment
    from django.conf import settings
    if settings.STRIPE_ENABLED and cohort.minimum_price_cents > 0:
        return redirect('payments:create_checkout', cohort_id=cohort.id)
    
    # Otherwise, redirect to entry survey
    return redirect('surveys:entry_survey', cohort_id=cohort.id)


def join_start(request: HttpRequest) -> HttpResponse:
    """Step 1: Account creation or login for cohort enrollment."""
    # If user is authenticated, redirect to checkout
    if request.user.is_authenticated:
        # Check if already enrolled in active cohort
        today = timezone.now().date()
        active_enrollment = Enrollment.objects.filter(
            user=request.user,
            cohort__is_active=True,
            cohort__start_date__gte=today - timezone.timedelta(days=7)
        ).select_related('cohort').first()
        
        if active_enrollment:
            return redirect('cohorts:homepage')
        
        # Otherwise redirect to checkout
        return redirect('cohorts:join_checkout')
    
    # Get next active cohort
    today = timezone.now().date()
    next_cohort = Cohort.objects.filter(
        is_active=True,
        start_date__gte=today
    ).order_by('start_date').first()
    
    context = {
        'cohort': next_cohort,
        'login_form': LoginForm(),
        'signup_form': SignupForm(),
    }
    
    return render(request, 'cohorts/join_start.html', context)


@login_required
def join_checkout(request: HttpRequest) -> HttpResponse:
    """Step 2: Payment checkout (or skip if free cohort)."""
    from django.conf import settings
    from .forms import PaymentAmountForm
    
    # Get next active cohort
    today = timezone.now().date()
    cohort = Cohort.objects.filter(
        is_active=True,
        start_date__gte=today - timezone.timedelta(days=7)
    ).order_by('start_date').first()
    
    if not cohort:
        return render(request, 'cohorts/cohort_join_error.html', {
            'message': 'No active cohorts available at the moment.'
        })
    
    # Check if cohort is full
    if cohort.is_full():
        return render(request, 'cohorts/cohort_join_error.html', {
            'cohort': cohort,
            'message': f'This cohort is full. Please check back for the next cohort.'
        })
    
    # Check if already enrolled
    existing_enrollment = Enrollment.objects.filter(
        user=request.user,
        cohort=cohort
    ).first()
    
    if existing_enrollment and existing_enrollment.status in ['paid', 'free']:
        return redirect('cohorts:homepage')
    
    # If free cohort, create enrollment and redirect to success
    if not cohort.is_paid:
        enrollment, created = Enrollment.objects.get_or_create(
            user=request.user,
            cohort=cohort,
            defaults={'status': 'free'}
        )
        if created or enrollment.status == 'pending':
            enrollment.status = 'free'
            enrollment.save()
        return redirect('cohorts:join_success')
    
    # Paid cohort - show payment form
    if request.method == 'POST':
        form = PaymentAmountForm(request.POST, minimum_price_cents=cohort.minimum_price_cents)
        if form.is_valid():
            amount_cents = form.cleaned_data['amount_cents']
            # Create or get enrollment
            enrollment, created = Enrollment.objects.get_or_create(
                user=request.user,
                cohort=cohort,
                defaults={'status': 'pending'}
            )
            # Redirect to Stripe checkout
            from django.urls import reverse
            return redirect(
                reverse('payments:create_checkout', kwargs={'cohort_id': cohort.id}) + 
                f'?amount={amount_cents}'
            )
    else:
        form = PaymentAmountForm(minimum_price_cents=cohort.minimum_price_cents)
    
    context = {
        'cohort': cohort,
        'form': form,
        'minimum_price_dollars': cohort.minimum_price_cents / 100,
    }
    
    return render(request, 'cohorts/join_checkout.html', context)


@login_required
def join_success(request: HttpRequest) -> HttpResponse:
    """Step 3: Onboarding success page after enrollment."""
    # Get user's most recent enrollment
    enrollment = Enrollment.objects.filter(
        user=request.user
    ).select_related('cohort').order_by('-enrolled_at').first()
    
    if not enrollment:
        return redirect('cohorts:homepage')
    
    context = {
        'enrollment': enrollment,
        'cohort': enrollment.cohort,
    }
    
    return render(request, 'cohorts/join_success.html', context)

