from django.urls import path
from . import views

app_name = 'surveys'

urlpatterns = [
    path('cohorts/<int:cohort_id>/surveys/<slug:survey_slug>/submissions/new/<str:due_date>/', views.survey_view, name='new_submission'),
    path('cohorts/<int:cohort_id>/surveys/<slug:survey_slug>/submissions/', views.past_submission_view, name='submission_list'),
]
