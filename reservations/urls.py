from django.urls import path, include
from rest_framework_nested.routers import DefaultRouter, NestedSimpleRouter
from .views import GuestViewSet, ReservationViewSet, GuestDocumentViewSet

# Main router
router = DefaultRouter()
router.register(r'guests', GuestViewSet, basename='guest')
router.register(r'reservations', ReservationViewSet, basename='reservation')

# Nested router for guest documents
# This will create URLs like: /guests/{guest_pk}/documents/
guest_documents_router = NestedSimpleRouter(router, r'guests', lookup='guest')
guest_documents_router.register(r'documents', GuestDocumentViewSet, basename='guest-document')
# Note: basename for GuestDocumentViewSet is 'guest-document'
# URL names will be like: guest-document-list, guest-document-detail, guest-document-verify

urlpatterns = [
    path('', include(router.urls)),
    path('', include(guest_documents_router.urls)),
]
