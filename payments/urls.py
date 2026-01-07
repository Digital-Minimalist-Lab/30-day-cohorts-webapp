from django.urls import path
from .views import  create_checkout_session, payment_success, payment_cancel, stripe_webhook

app_name = 'payments'

urlpatterns = [
    path('create-checkout/<int:cohort_id>/', create_checkout_session, name='create_checkout'),
    path('success/', payment_success, name='success'),
    path('cancel/', payment_cancel, name='cancel'),
    path('webhooks/stripe/', stripe_webhook, name='webhook'),
]

