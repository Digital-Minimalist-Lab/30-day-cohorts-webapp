from django.urls import path
import os
from .views import onboarding, surveys, dashboard

app_name = 'cohorts'

urlpatterns = [
    path('', dashboard.dashboard, name='dashboard'),
    path('dashboard/', dashboard.dashboard, name='dashboard'),

    path('cohort/', dashboard.dashboard, name='enrollment_landing'),  # Alias for dashboard

    # onboarding
    path('cohort/join/start/', onboarding.join_start, name='join_start'),
    path('cohort/join/entry-survey/', onboarding.join_entry_survey, name='join_entry_survey'),
    path('cohort/join/checkout/', onboarding.join_checkout, name='join_checkout'),
    path('cohort/join/success/', onboarding.join_success, name='join_success'),
    path('cohorts/<int:cohort_id>/join/', onboarding.cohort_join, name='cohort_join'),

    # surveys
    path('cohorts/<int:cohort_id>/surveys/<slug:survey_slug>/submissions/new/<str:due_date>/', surveys.survey_view, name='new_submission'),

    # special case for onboarding survey
    path('cohorts/<int:cohort_id>/surveys/<slug:survey_slug>/onboarding/<str:due_date>/', surveys.onboarding_survey_view, name='onboarding_entry_survey'),
    path('cohorts/<int:cohort_id>/surveys/<slug:survey_slug>/submissions/', surveys.PastSubmissionsListView.as_view(), name='submission_list'),
]
