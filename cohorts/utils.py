import pytz
from django.contrib.auth.models import AbstractUser
from datetime import date
from django.utils import timezone

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

