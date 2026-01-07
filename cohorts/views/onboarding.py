from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.conf import settings
from django.urls import reverse

from ..models import Cohort, Enrollment, UserSurveyResponse
from ..forms import PaymentAmountForm
from ..decorators import enrollment_required

from surveys.models import Survey

import logging
logger = logging.getLogger(__name__)


def generate_quick_select_amounts(minimum_price_cents: int) -> list[int]:
    """
    Generate quick select payment amounts based on pricing psychology.

    Uses a gentler progression (1.5-2x multipliers) to create reasonable options
    that feel like meaningful choices without being overwhelming.

    Research basis:
    - Offer 4 options (optimal for choice without paralysis)
    - Use ~1.5-2x multipliers (creates clear tiers without huge jumps)
    - Round to "charm prices" (5, 10, 15, 20, 25, 30, 50, 75, 100)

    Args:
        minimum_price_cents: Minimum price in cents

    Returns:
        List of 3-4 dollar amounts (integers)
    """
    min_dollars = minimum_price_cents / 100
    min_dollars_scale = 2.75

    def round_to_friendly(amount: float) -> float:
        """Round to psychologically appealing price points."""
        if amount == 0: 
            return 0

        if amount <= 1:
            return 1
        if amount <= 5:
            return 5
        elif amount <= 10:
            return 10
        elif amount <= 15:
            return 15
        elif amount <= 20:
            return 20
        elif amount <= 25:
            return 25
        elif amount <= 30:
            return 30
        elif amount <= 40:
            return 40
        elif amount <= 50:
            return 50
        elif amount <= 75:
            return 75
        elif amount <= 100:
            return 100
        elif amount <= 150:
            return 150
        elif amount <= 200:
            return 200
        else:
            # Round to nearest 50 for larger amounts
            return int(round(amount / 50) * 50)

    # Generate 4 options with gentle progression
    quick_select_amounts = [round_to_friendly(min_dollars)]
    
    base = max(min_dollars_scale, min_dollars)
    multipliers = [1.25, 2, 3, 4]
    current_mult_idx = 0

    # Keep generating until we have exactly 4 unique options
    while len(quick_select_amounts) < 4:
        if current_mult_idx < len(multipliers):
            mult = multipliers[current_mult_idx]
        else:
            # If we run out of multipliers or have collisions, keep scaling up
            # Add 0.75 to the last multiplier for each new step
            mult = multipliers[-1] + (0.75 * (current_mult_idx - len(multipliers) + 1))
        
        val = round_to_friendly(base * mult)
        
        # Only add if it's strictly greater than the last amount (ensures uniqueness and order)
        if val > quick_select_amounts[-1]:
            quick_select_amounts.append(val)
            
        current_mult_idx += 1

    return quick_select_amounts


@login_required
def cohort_join(request: HttpRequest, cohort_id: int) -> HttpResponse:
    """Join a cohort (with or without payment)."""
    # Find the specific cohort from the list of joinable cohorts.
    # This is more efficient as it reuses the manager's logic.
    joinable_cohorts = Cohort.objects.get_joinable()
    cohort = next((c for c in joinable_cohorts if c.id == cohort_id), None)

    if not cohort:
        # If not found, fetch it to provide a specific error message.
        cohort = get_object_or_404(Cohort, id=cohort_id)
        return render(request, 'cohorts/join_error.html', {
            'cohort': cohort,
            'message': f'This cohort is not currently accepting new members. The enrollment period may be over, or it might be full.'
        })
    
    # Check if already enrolled
    enrollment, created = Enrollment.objects.get_or_create(
        user=request.user,
        cohort=cohort
    )
    
    if enrollment.status != 'pending':
        return redirect('cohorts:dashboard')
    
    # If payment is enabled, redirect to payment
    if settings.STRIPE_ENABLED and cohort.minimum_price_cents > 0:
        return redirect('payments:create_checkout', cohort_id=cohort.id)
    
    # Otherwise, redirect to entry survey
    return redirect('surveys:entry_survey', cohort_id=cohort.id)


def join_start(request: HttpRequest) -> HttpResponse:
    """Step 1: Account creation or login for cohort enrollment."""
    if request.user.is_authenticated:
        return redirect('cohorts:join_entry_survey')

    # For unauthenticated users, redirect to the standard allauth signup page.
    # We pass 'next' to ensure they land on the entry survey after signup.
    return redirect(reverse('account_signup') + f"?next={reverse('cohorts:join_entry_survey')}")


@login_required
def join_entry_survey(request: HttpRequest) -> HttpResponse:
    """Step 2: Entry survey before checkout."""

    # Find the next upcoming or recently started cohort
    cohort = next(iter(Cohort.objects.get_joinable()), None)

    if not cohort:
        return render(request, 'cohorts/join_error.html', {
            'message': 'No active cohorts available at the moment.'
        })

    # Check if cohort is full
    if cohort.is_full():
        return render(request, 'cohorts/join_error.html', {
            'cohort': cohort,
            'message': f'This cohort is full. Please check back for the next cohort.'
        })

    # Create pending enrollment if it doesn't exist
    Enrollment.objects.get_or_create(
        user=request.user,
        cohort=cohort,
        defaults={'status': 'pending'}
    )

    # If already completed entry survey, skip to checkout
    entry_survey = cohort.onboarding_survey
    if entry_survey:
        has_completed_entry = UserSurveyResponse.objects.filter(
            user=request.user,
            cohort=cohort,
            submission__survey=entry_survey
        ).exists()

        if has_completed_entry:
            return redirect('cohorts:join_checkout')

    # Get entry survey and redirect to the onboarding entry survey view
    if not entry_survey:
        # No entry survey configured, skip to checkout
        return redirect('cohorts:join_checkout')

    # Redirect to the entry survey with special onboarding handling
    # The view will look up the scheduler from cohort.onboarding_survey
    return redirect('cohorts:onboarding_entry_survey', cohort_id=cohort.id)


@login_required
def join_checkout(request: HttpRequest) -> HttpResponse:
    """Step 3: Payment checkout (or skip if free cohort)."""

    # Find the next upcoming or recently started cohort
    cohort = next(iter(Cohort.objects.get_joinable()), None)

    if not cohort:
        return render(request, 'cohorts/join_error.html', {
            'message': 'No active cohorts available at the moment.'
        })

    # Check if cohort is full
    if cohort.is_full():
        return render(request, 'cohorts/join_error.html', {
            'cohort': cohort,
            'message': f'This cohort is full. Please check back for the next cohort.'
        })

    # Check if already enrolled
    existing_enrollment = Enrollment.objects.filter(
        user=request.user,
        cohort=cohort
    ).first()

    if existing_enrollment and existing_enrollment.status in ['paid', 'free']:
        return redirect('cohorts:dashboard')

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

            if amount_cents > 0:
                # Redirect to Stripe checkout
                return redirect(
                    reverse('payments:create_checkout', kwargs={'cohort_id': cohort.id}) +
                    f'?amount={amount_cents}'
                )
            else:
                # Free enrollment
                enrollment.status = 'paid'
                enrollment.amount_paid_cents = 0
                enrollment.save()
                return redirect('cohorts:join_success')

    else:
        form = PaymentAmountForm(minimum_price_cents=cohort.minimum_price_cents)

    price = cohort.minimum_price_cents / 100
    price = 100
    context = {
        'cohort': cohort,
        'form': form,
        'minimum_price_dollars': price / 100,
        'quick_select_amounts': generate_quick_select_amounts(price),
    }

    return render(request, 'cohorts/join_checkout.html', context)


@login_required
@enrollment_required
def join_success(request: HttpRequest, *args, **kwargs) -> HttpResponse:
    """Step 4: Onboarding success page after enrollment."""
    return render(request, 'cohorts/join_success.html', kwargs['context'])
