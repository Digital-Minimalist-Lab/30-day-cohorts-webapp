from django.urls import path
import os
from .views import cohorts, surveys, dashboard

app_name = 'cohorts'

if 'LANDING_ONLY' not in os.environ:
    urlpatterns = [
        path('', dashboard.homepage, name='homepage'),
        path('dashboard/', dashboard.homepage, name='homepage'),
        
        path('cohort/', dashboard.homepage, name='enrollment_landing'),  # Alias for homepage
        path('cohort/join/start/', cohorts.join_start, name='join_start'),
        path('cohort/join/checkout/', cohorts.join_checkout, name='join_checkout'),
        path('cohort/join/success/', cohorts.join_success, name='join_success'),
        path('cohorts/', cohorts.cohort_list, name='cohort_list'),
        path('cohorts/<int:cohort_id>/join/', cohorts.cohort_join, name='cohort_join'),

        path('cohorts/<int:cohort_id>/surveys/<slug:survey_slug>/submissions/new/<str:due_date>/', surveys.survey_view, name='new_submission'),
        path('cohorts/<int:cohort_id>/surveys/<slug:survey_slug>/submissions/', surveys.PastSubmissionsListView.as_view(), name='submission_list'),
    ]

else:
    urlpatterns = [
        path('', dashboard.landing, name='landing'),
    ]
