from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GuestViewSet, ReservationViewSet

router = DefaultRouter()
router.register(r'guests', GuestViewSet)
router.register(r'reservations', ReservationViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
