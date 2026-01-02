from django.urls import path
from . import views

app_name = 'surveys'

urlpatterns = [
    path('<slug:slug>/', views.survey_preview, name='survey_preview'),
]
