from django.urls import path
from .views import profile_view, export_user_data, delete_account, privacy_policy, protocol_view, resources_view
from .views import CustomLoginView, CustomSignupView

app_name = 'accounts'

urlpatterns = [
    path('profile/', profile_view, name='profile'),
    path('export-data/', export_user_data, name='export_data'),
    path('delete-account/', delete_account, name='delete_account'),
    path('privacy/', privacy_policy, name='privacy'),
    path('protocol/', protocol_view, name='protocol'),
    path('resources/', resources_view, name='resources'),

    path('login/', CustomLoginView.as_view(), name='account_login'),
    path('signup/', CustomSignupView.as_view(), name='account_signup'),
]
