"""
URL configuration for digital minimalist cohorts project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from core import urls as core_urls

if settings.LANDING_ONLY:
    urlpatterns = [
        path('', include(core_urls)),
    ]
else:
    from health_check import urls as health_check_urls
    from accounts import urls as accounts_urls
    from allauth import urls as allauth_urls
    from payments import urls as payments_urls
    from cohorts import urls as cohorts_urls
    from accounts import api_urls as accounts_api_urls
    from surveys import urls as surveys_urls
    import djstripe.urls

    urlpatterns = [
        path('health/', include(health_check_urls)),
        path('admin/', admin.site.urls),
        path('api/accounts/', include(accounts_api_urls)),
        path('accounts/', include(accounts_urls)),
        path('accounts/', include(allauth_urls)),
        path('payments/', include(payments_urls)),
        path('stripe/', include(djstripe.urls)),
        path('surveys/', include(surveys_urls)),
        path('', include(cohorts_urls)),
        path('', include(core_urls)),
    ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
