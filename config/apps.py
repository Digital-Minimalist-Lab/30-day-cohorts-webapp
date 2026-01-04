from django.apps import AppConfig
from django.db.models.signals import post_migrate

import logging as log
logger = log.getLogger(__name__)

def setup_site_domain(sender, **kwargs):
    """
    Updates the default Site object with the configured domain and name.
    This runs after migrations to ensure the DB matches settings.
    """
    # Only run when the 'sites' app is migrated/synced
    if sender.name != 'django.contrib.sites':
        return

    from django.contrib.sites.models import Site
    from django.conf import settings

    try:
        # Update the default site (ID=1) to match settings
        Site.objects.update_or_create(
            pk=settings.SITE_ID,
            defaults={
                'domain': settings.SITE_DOMAIN,
                'name': settings.SITE_NAME,
            }
        )
        logger.info(f"✅ Site configuration updated: {settings.SITE_DOMAIN}")
    except Exception as e:
        logger.error(f"⚠️ Could not update Site: {e}")


class ConfigConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'config'

    def ready(self):
        post_migrate.connect(setup_site_domain)
