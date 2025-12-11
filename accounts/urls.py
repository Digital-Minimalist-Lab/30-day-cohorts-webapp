from django.urls import path
from .views import profile_view, export_user_data, delete_account, request_login_code_redirect, login_by_code_view

app_name = 'accounts'

urlpatterns = [
    path('login/code/', request_login_code_redirect, name='account_request_login_code'),
    path('login/code/use/', login_by_code_view, name='account_login_by_code_url'),

    path('profile/', profile_view, name='profile'),
    path('export-data/', export_user_data, name='export_data'),
    path('delete-account/', delete_account, name='delete_account'),
]
