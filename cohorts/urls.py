from django.urls import path
import os
from . import views
from . import survey_views

app_name = 'cohorts'

if 'LANDING_ONLY' not in os.environ:
    urlpatterns = [
        path('', views.homepage, name='homepage'),
        path('cohort/', views.homepage, name='enrollment_landing'),  # Alias for homepage
        path('cohort/join/start/', views.join_start, name='join_start'),
        path('cohort/join/checkout/', views.join_checkout, name='join_checkout'),
        path('cohort/join/success/', views.join_success, name='join_success'),
        path('cohorts/', views.cohort_list, name='cohort_list'),
        path('cohorts/<int:cohort_id>/join/', views.cohort_join, name='cohort_join'),

        path('cohorts/<int:cohort_id>/surveys/<slug:survey_slug>/submissions/new/<str:due_date>/', survey_views.survey_view, name='new_submission'),
        path('cohorts/<int:cohort_id>/surveys/<slug:survey_slug>/submissions/', survey_views.PastSubmissionsListView.as_view(), name='submission_list'),

    ]

else:
    urlpatterns = [
        path('', views.landing, name='landing'),
    ]

