from django.urls import path
from .views import privacy_policy, protocol_view, resources_view, landing

app_name = 'core'

urlpatterns = [
    path('privacy/', privacy_policy, name='privacy'),
    path('protocol/', protocol_view, name='protocol'),
    path('resources/', resources_view, name='resources'),
    path('', landing, name='index_landing'),
    path('landing/', landing, name='landing'),
]
