from django.urls import path, include
from .views import  create_checkout_session, payment_success, payment_cancel
#import djstripe.urls

app_name = 'payments'

urlpatterns = [
    path('create-checkout/<int:cohort_id>/', create_checkout_session, name='create_checkout'),
    path('success/', payment_success, name='success'),
    path('cancel/', payment_cancel, name='cancel'),
    #path('stripe/', include(djstripe.urls, namespace='djstripe')),
]
