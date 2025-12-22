from typing import Any
from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site


class Command(BaseCommand):
    help = 'Set up the default site for django-allauth'

    def handle(self, *args: Any, **options: Any) -> None:
        """Create or update the default site."""
        site, created = Site.objects.get_or_create(pk=1)
        if created:
            site.domain = 'localhost:8000'
            site.name = 'Intentional Tech'
            site.save()
            self.stdout.write(
                self.style.SUCCESS('Created default site (localhost:8000)')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('Default site already exists')
            )

