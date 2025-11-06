from django.urls import path
from . import views

app_name = 'surveys'

urlpatterns = [
    path('entry/<int:cohort_id>/', views.entry_survey, name='entry_survey'),
    path('exit/<int:cohort_id>/', views.exit_survey, name='exit_survey'),
]

