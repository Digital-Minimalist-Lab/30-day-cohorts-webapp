from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpRequest
from django.conf import settings
from django.contrib import messages
from django.contrib.sites.shortcuts import get_current_site
from django.db.models import Sum
from cohorts.models import Cohort, Enrollment
from .models import Order, OrderItem
import stripe
import logging

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


@login_required
def create_checkout_session(request: HttpRequest, cohort_id: int) -> HttpResponse:
    """Create Stripe checkout session for cohort payment."""
    if not settings.STRIPE_LIVE_MODE:
        messages.error(request, 'Payments are not enabled in this environment.')
        return redirect('cohorts:dashboard')
    
    cohort = get_object_or_404(Cohort, id=cohort_id)
    
    # Check if already paid
    enrollment = Enrollment.objects.filter(user=request.user, cohort=cohort).first()
    if enrollment and enrollment.status in ['paid', 'free']:
        messages.info(request, 'You have already enrolled in this cohort.')
        return redirect('cohorts:dashboard')
    
    # Get custom amount from query parameter (in cents)
    amount_cents = request.GET.get('amount')
    if amount_cents:
        try:
            amount_cents = int(amount_cents)
            if amount_cents < cohort.minimum_price_cents:
                amount_cents = cohort.minimum_price_cents
        except (ValueError, TypeError):
            amount_cents = cohort.minimum_price_cents
    else:
        amount_cents = cohort.minimum_price_cents
    
    current_site = get_current_site(request)
    protocol = request.scheme
    site_url = f"{protocol}://{current_site.domain}"

    try:
        # Create a pending Order
        # NOTE: For group buying, you would create multiple OrderItems here based on form input
        with transaction.atomic():
            order = Order.objects.create(
                user=request.user,
                total_amount_cents=amount_cents,
                status='pending'
            )
            OrderItem.objects.create(
                order=order,
                content_object=cohort,
                recipient_email=request.user.email, # Default to self for now
                price_cents=amount_cents
            )

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': amount_cents,
                    'product_data': {
                        'name': cohort.name,
                        'description': f'30-Day Digital Declutter Cohort ({cohort.start_date} - {cohort.end_date})',
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=site_url + '/cohort/join/success/',
            cancel_url=site_url + '/cohort/join/checkout/',
            client_reference_id=f'ORDER:{order.id}',
            metadata={
                'user_id': request.user.id,
                'cohort_id': cohort.id,
                'amount_cents': amount_cents,
            }
        )
        return redirect(checkout_session.url)
    except stripe.error.StripeError as e:
        # Log the actual error server-side
        logger.error(f"Stripe error for user {request.user.id}, cohort {cohort.id}: {str(e)}")
        # Show generic message to user (don't expose Stripe details)
        messages.error(request, 'Unable to process payment at this time. Please try again later or contact support.')
        return redirect('cohorts:join_checkout')
    except Exception as e:
        # Log unexpected errors
        logger.error(f"Unexpected payment error for user {request.user.id}, cohort {cohort.id}: {str(e)}")
        messages.error(request, 'An unexpected error occurred. Please try again later.')
        return redirect('cohorts:join_checkout')


@login_required
def payment_success(request: HttpRequest) -> HttpResponse:
    """Payment success page."""
    session_id = request.GET.get('session_id')
    return render(request, 'payments/success.html', {
        'session_id': session_id,
    })


@login_required
def payment_cancel(request: HttpRequest) -> HttpResponse:
    """Payment cancelled page."""
    return render(request, 'payments/cancel.html')
