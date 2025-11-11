from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpRequest
from django.conf import settings
from django.contrib import messages
from cohorts.models import Cohort, Enrollment
import stripe
import logging

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


@login_required
def create_checkout_session(request: HttpRequest, cohort_id: int) -> HttpResponse:
    """Create Stripe checkout session for cohort payment."""
    if not settings.STRIPE_ENABLED:
        messages.error(request, 'Payments are not enabled.')
        return redirect('cohorts:cohort_list')
    
    cohort = get_object_or_404(Cohort, id=cohort_id)
    
    # Check if already paid
    enrollment = Enrollment.objects.filter(user=request.user, cohort=cohort).first()
    if enrollment and enrollment.status in ['paid', 'free']:
        messages.info(request, 'You have already enrolled in this cohort.')
        return redirect('cohorts:homepage')
    
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
    
    try:
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
            success_url=settings.SITE_URL + '/cohort/join/success/',
            cancel_url=settings.SITE_URL + '/cohort/join/checkout/',
            client_reference_id=f'{request.user.id}:{cohort.id}:{amount_cents}',
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


@csrf_exempt
def stripe_webhook(request: HttpRequest) -> HttpResponse:
    """Handle Stripe webhooks for payment confirmation."""
    if not settings.STRIPE_ENABLED:
        return HttpResponse(status=400)
    
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)
    
    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        # Parse client_reference_id (format: "user_id:cohort_id:amount_cents")
        client_ref = session.get('client_reference_id', '')
        if ':' in client_ref:
            parts = client_ref.split(':')
            if len(parts) >= 3:
                user_id, cohort_id, amount_cents = parts[0], parts[1], parts[2]
            else:
                # Legacy format without amount
                user_id, cohort_id = parts[0], parts[1]
                amount_cents = session.get('amount_total', 0)
            
            try:
                from django.contrib.auth import get_user_model
                from django.utils import timezone
                User = get_user_model()
                user = User.objects.get(id=user_id)
                cohort = Cohort.objects.get(id=cohort_id)
                
                # Update enrollment with payment details
                enrollment, created = Enrollment.objects.get_or_create(
                    user=user,
                    cohort=cohort
                )
                
                # Only update if not already paid (idempotency)
                if enrollment.status != 'paid':
                    enrollment.status = 'paid'
                    enrollment.amount_paid_cents = int(amount_cents)
                    enrollment.paid_at = timezone.now()
                    enrollment.save()
                    logger.info(
                        f"Payment confirmed for user {user.id}, cohort {cohort.id}, "
                        f"amount ${int(amount_cents)/100:.2f}"
                    )
                else:
                    logger.info(f"Duplicate webhook for user {user.id}, cohort {cohort.id} - already paid")
            except Exception as e:
                # Log error without exposing sensitive data
                logger.error(f"Webhook processing error for client_ref {client_ref}: {str(e)}")
    
    return HttpResponse(status=200)

