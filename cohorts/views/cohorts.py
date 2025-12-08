from typing import Optional
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AbstractUser
from django.http import HttpRequest, HttpResponse
from allauth.account.forms import LoginForm, SignupForm
from django.conf import settings
from django.urls import reverse

from ..models import Cohort, Enrollment
from ..forms import PaymentAmountForm

import logging
logger = logging.getLogger(__name__)

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



@login_required
def cohort_list(request: HttpRequest) -> HttpResponse:
    """List available cohorts."""
    # Get cohorts that can be joined (within 7 days of start and active)
    available_cohorts = Cohort.objects.get_joinable()

    # Get user's enrollments
    user_enrollments = Enrollment.objects.filter(
        user=request.user
    ).exclude(status='pending').values_list('cohort_id', flat=True)
    
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
    if settings.STRIPE_ENABLED and cohort.minimum_price_cents > 0:
        return redirect('payments:create_checkout', cohort_id=cohort.id)
    
    # Otherwise, redirect to entry survey
    return redirect('surveys:entry_survey', cohort_id=cohort.id)


def join_start(request: HttpRequest) -> HttpResponse:
    """Step 1: Account creation or login for cohort enrollment."""
    # If user is authenticated, redirect to checkout
    # Find the next upcoming or recently started cohort
    joinable_cohort = Cohort.objects.get_joinable().first() or Cohort.objects.get_upcoming().first()

    if request.user.is_authenticated:
        # If user is already enrolled in the target cohort, redirect to homepage
        if joinable_cohort and Enrollment.objects.filter(user=request.user, cohort=joinable_cohort).exists():
            return redirect('cohorts:homepage')
        
        # Otherwise redirect to checkout
        return redirect('cohorts:join_checkout')
    
    context = {
        'cohort': joinable_cohort,
        'login_form': LoginForm(),
        'signup_form': SignupForm(),
    }
    
    return render(request, 'cohorts/join_start.html', context)


@login_required
def join_checkout(request: HttpRequest) -> HttpResponse:
    """Step 2: Payment checkout (or skip if free cohort)."""
    
    # Find the next upcoming or recently started cohort
    cohort = Cohort.objects.get_joinable().first() or Cohort.objects.get_upcoming().first()

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
