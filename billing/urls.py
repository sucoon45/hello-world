from django.urls import path, include
from rest_framework_nested.routers import DefaultRouter, NestedSimpleRouter
from .views import InvoiceViewSet, PaymentViewSet

router = DefaultRouter()
router.register(r'invoices', InvoiceViewSet, basename='invoice')

# Nested router for payments under invoices
# /invoices/{invoice_pk}/payments/
payments_router = NestedSimpleRouter(router, r'invoices', lookup='invoice')
payments_router.register(r'payments', PaymentViewSet, basename='invoice-payment')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(payments_router.urls)),
]
