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
    if enrollment and enrollment.paid_at:
        messages.info(request, 'You have already paid for this cohort.')
        return redirect('cohorts:homepage')
    
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': cohort.price_cents,
                    'product_data': {
                        'name': cohort.name,
                        'description': f'30-Day Digital Declutter Cohort ({cohort.start_date} - {cohort.end_date})',
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=settings.SITE_URL + '/payments/success/?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=settings.SITE_URL + '/payments/cancel/',
            client_reference_id=f'{request.user.id}:{cohort.id}',
        )
        return redirect(checkout_session.url)
    except stripe.error.StripeError as e:
        # Log the actual error server-side
        logger.error(f"Stripe error for user {request.user.id}, cohort {cohort.id}: {str(e)}")
        # Show generic message to user (don't expose Stripe details)
        messages.error(request, 'Unable to process payment at this time. Please try again later or contact support.')
        return redirect('cohorts:cohort_list')
    except Exception as e:
        # Log unexpected errors
        logger.error(f"Unexpected payment error for user {request.user.id}, cohort {cohort.id}: {str(e)}")
        messages.error(request, 'An unexpected error occurred. Please try again later.')
        return redirect('cohorts:cohort_list')


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
        
        # Parse client_reference_id (format: "user_id:cohort_id")
        client_ref = session.get('client_reference_id', '')
        if ':' in client_ref:
            user_id, cohort_id = client_ref.split(':')
            
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(id=user_id)
                cohort = Cohort.objects.get(id=cohort_id)
                
                # Update enrollment with payment timestamp
                enrollment, created = Enrollment.objects.get_or_create(
                    user=user,
                    cohort=cohort
                )
                if not enrollment.paid_at:
                    from django.utils import timezone
                    enrollment.paid_at = timezone.now()
                    enrollment.save()
                    logger.info(f"Payment confirmed for user {user.id}, cohort {cohort.id}")
            except Exception as e:
                # Log error without exposing sensitive data
                logger.error(f"Webhook processing error for client_ref {client_ref}: {str(e)}")
    
    return HttpResponse(status=200)

