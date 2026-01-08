from django.dispatch import receiver, Signal
from django.db import transaction
from djstripe.signals import WEBHOOK_SIGNALS
from .models import Order
import logging

logger = logging.getLogger(__name__)

# Define a signal that other apps can listen to
# Provides arguments: order
order_paid = Signal()

@receiver(WEBHOOK_SIGNALS['checkout.session.completed'])
def handle_checkout_session_completed(sender, event, **kwargs):
    """
    Handle the checkout.session.completed event from Stripe.
    This is triggered by dj-stripe after it verifies the webhook.

    Args:
        sender: The dj-stripe Event model class
        event: The dj-stripe Event instance containing the webhook data
        **kwargs: Additional keyword arguments
    """
    # Get the session data from the event
    # dj-stripe provides the event object which has a 'data' attribute
    session_data = event.data.get('object', {}) if hasattr(event, 'data') else event.get('data', {}).get('object', {})
    client_ref = session_data.get('client_reference_id', '')

    logger.info(f"Processing checkout session for ref: {client_ref}")

    if client_ref.startswith('ORDER:'):
        try:
            order_id = client_ref.split(':')[1]
            order = Order.objects.get(id=order_id)

            # Validate that the amount paid matches the order total
            amount_paid = session_data.get('amount_total') or 0
            if amount_paid < order.total_amount_cents:
                logger.warning(
                    f"Insufficient payment for Order {order.id}: Paid {amount_paid}, Expected {order.total_amount_cents}"
                )
                return

            # Mark order as paid
            with transaction.atomic():
                order.status = 'paid'
                order.save()

                # Notify other apps that the order is paid
                order_paid.send(sender=Order, order=order)

        except Exception as e:
            logger.error(f"Error processing order {client_ref}: {e}")
