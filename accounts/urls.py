from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.health_check, name='health_check'),
    path('settings/', views.settings_view, name='settings'),
    path('export-data/', views.export_user_data, name='export_data'),
    path('delete-account/', views.delete_account, name='delete_account'),
    path('privacy/', views.privacy_policy, name='privacy'),
    path('protocol/', views.protocol_view, name='protocol'),
    path('resources/', views.resources_view, name='resources'),
]

