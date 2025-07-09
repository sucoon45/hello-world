from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RoomTypeViewSet, AmenityViewSet, RoomViewSet

router = DefaultRouter()
router.register(r'roomtypes', RoomTypeViewSet)
router.register(r'amenities', AmenityViewSet)
router.register(r'rooms', RoomViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
