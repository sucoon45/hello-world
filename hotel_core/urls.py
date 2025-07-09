from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RoomTypeViewSet, AmenityViewSet, RoomViewSet,
    SeasonalPricingViewSet, RoomServiceRequestViewSet, CleaningAssignmentViewSet # Added CleaningAssignmentViewSet
)

router = DefaultRouter()
router.register(r'roomtypes', RoomTypeViewSet, basename='roomtype')
router.register(r'amenities', AmenityViewSet, basename='amenity')
router.register(r'rooms', RoomViewSet, basename='room')
router.register(r'seasonal-pricing', SeasonalPricingViewSet, basename='seasonalpricing')
router.register(r'room-service-requests', RoomServiceRequestViewSet, basename='roomservicerequest')
router.register(r'cleaning-assignments', CleaningAssignmentViewSet, basename='cleaningassignment')


urlpatterns = [
    path('', include(router.urls)),
]
