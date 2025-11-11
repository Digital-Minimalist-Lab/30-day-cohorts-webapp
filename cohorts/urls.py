from django.urls import path
from . import views

app_name = 'cohorts'

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('cohort/', views.homepage, name='enrollment_landing'),  # Alias for homepage
    path('cohort/join/start/', views.join_start, name='join_start'),
    path('cohort/join/checkout/', views.join_checkout, name='join_checkout'),
    path('cohort/join/success/', views.join_success, name='join_success'),
    path('cohorts/', views.cohort_list, name='cohort_list'),
    path('cohorts/<int:cohort_id>/join/', views.cohort_join, name='cohort_join'),
]

