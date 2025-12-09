from django.urls import path
from .views import CustomLoginView, CustomSignupView
from .views import profile_view, export_user_data, delete_account

app_name = 'accounts'

urlpatterns = [
    path('profile/', profile_view, name='profile'),
    path('export-data/', export_user_data, name='export_data'),
    path('delete-account/', delete_account, name='delete_account'),
    path('login/', CustomLoginView.as_view(), name='account_login'),
    path('signup/', CustomSignupView.as_view(), name='account_signup'),
]
