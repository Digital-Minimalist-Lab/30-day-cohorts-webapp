from django.urls import path
from . import views

app_name = 'checkins'

urlpatterns = [
    path('daily/<int:cohort_id>/', views.daily_checkin, name='daily_checkin'),
    path('weekly/<int:cohort_id>/', views.weekly_reflection, name='weekly_reflection'),
    path('past-checkins/<int:cohort_id>/', views.past_checkins, name='past_checkins'),
    path('past-reflections/<int:cohort_id>/', views.past_reflections, name='past_reflections'),
]

