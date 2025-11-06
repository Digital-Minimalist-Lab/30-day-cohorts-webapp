from django.urls import path
from . import views

app_name = 'admin_tools'

urlpatterns = [
    path('users/', views.user_list, name='user_list'),
    path('export/<int:cohort_id>/', views.export_cohort_csv, name='export_cohort_csv'),
    path('cohorts/create/', views.create_cohort, name='create_cohort'),
]

