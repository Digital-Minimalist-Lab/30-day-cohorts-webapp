from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from payments.signals import order_paid
from .models import Cohort, Enrollment
import logging

logger = logging.getLogger(__name__)

@receiver(order_paid)
def fulfill_cohort_order(sender, order, **kwargs):
    """
    Listen for paid orders and enroll users if the order contains a Cohort.
    """
    User = get_user_model()
    
    for item in order.items.all():
        # Check if the item bought is a Cohort
        if isinstance(item.content_object, Cohort):
            cohort = item.content_object
            recipient_email = item.recipient_email
            
            # Determine recipient user
            recipient = None
            if recipient_email == order.user.email:
                recipient = order.user
            else:
                # For group buys, find recipient by email
                recipient = User.objects.filter(email=recipient_email).first()
            
            if recipient:
                enrollment, created = Enrollment.objects.get_or_create(
                    user=recipient,
                    cohort=cohort,
                )
                
                # Update existing enrollment if necessary
                enrollment.status = 'paid'
                enrollment.paid_at = timezone.now()
                enrollment.amount_paid_cents = item.price_cents
                enrollment.save()
                
                logger.info(f"Enrolled {recipient.email} in {cohort.name}")
            else:
                logger.warning(f"Could not find user with email {recipient_email} for cohort enrollment")
