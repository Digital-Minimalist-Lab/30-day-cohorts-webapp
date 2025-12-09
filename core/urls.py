from django.urls import path
from .views import privacy_policy, protocol_view, resources_view

app_name = 'core'

urlpatterns = [
    path('privacy/', privacy_policy, name='privacy'),
    path('protocol/', protocol_view, name='protocol'),
    path('resources/', resources_view, name='resources'),
]
