from django.urls import path
from .views import health_check, profile_view, export_user_data, delete_account, privacy_policy, protocol_view, resources_view

app_name = 'accounts'

urlpatterns = [
    path('', health_check, name='health_check'),
    path('profile/', profile_view, name='profile'),
    path('export-data/', export_user_data, name='export_data'),
    path('delete-account/', delete_account, name='delete_account'),
    path('privacy/', privacy_policy, name='privacy'),
    path('protocol/', protocol_view, name='protocol'),
    path('resources/', resources_view, name='resources'),
]

