from django.urls import path
from .views import *

app_name = 'core'

urlpatterns = [
    path('privacy/', privacy_policy, name='privacy'),
    path('protocol/', protocol_view, name='protocol'),
    path('resources/', resources_view, name='resources'),
    path('', landing, name='index_landing'),
    path('landing/', landing, name='landing'),
    path('feedback/', feedback_view, name='feedback'),
    path('mailinglist/', mailinglist_view, name='mailinglist'),
    path('ui-design/', design_view, name='design'),
    path('ui-design/preview-task-email/<int:tasks>', preview_email, name='preview_email'),
]
