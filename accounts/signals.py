from typing import Any
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from .models import UserProfile

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(
    sender: type[AbstractUser],
    instance: AbstractUser,
    created: bool,
    **kwargs: Any
) -> None:
    """Create UserProfile when User is created."""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(
    sender: type[AbstractUser],
    instance: AbstractUser,
    **kwargs: Any
) -> None:
    """Save UserProfile when User is saved."""
    if hasattr(instance, 'profile'):
        instance.profile.save()

