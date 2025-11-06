from django.urls import path
from . import views

app_name = 'cohorts'

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('cohorts/', views.cohort_list, name='cohort_list'),
    path('cohorts/<int:cohort_id>/join/', views.cohort_join, name='cohort_join'),
]

