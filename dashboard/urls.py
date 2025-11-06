from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('data/', views.data_view, name='data_view'),
    path('data/chart-data/<int:cohort_id>/', views.chart_data, name='chart_data'),
]

