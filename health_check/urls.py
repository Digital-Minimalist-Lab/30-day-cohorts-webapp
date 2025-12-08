from django.urls import path
from .views import health_check

app_name = 'health_check'

urlpatterns = [
    path('', health_check, name='health_check'),
]
