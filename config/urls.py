"""
URL configuration for digital minimalist cohorts project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('', include('cohorts.urls')),
    path('surveys/', include('surveys.urls')),
    path('checkins/', include('checkins.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('payments/', include('payments.urls')),
    path('admin-tools/', include('admin_tools.urls')),
    path('health/', include('accounts.urls')),  # Health check and settings
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

