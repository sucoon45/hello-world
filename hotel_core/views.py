from rest_framework import viewsets, permissions
from .models import RoomType, Amenity, Room
from .serializers import RoomTypeSerializer, AmenitySerializer, RoomSerializer
# from django_filters.rest_framework import DjangoFilterBackend # For filtering
# from rest_framework import filters


# Basic permission: Allow read-only for anyone, but write operations only for admins/staff.
class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow admin users to edit objects.
    Read is allowed for anyone (authenticated or not for now, can be changed).
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS: # GET, HEAD, OPTIONS
            return True # Or use permissions.IsAuthenticated for read access
        return request.user and request.user.is_staff


class RoomTypeViewSet(viewsets.ModelViewSet):
    queryset = RoomType.objects.all()
    serializer_class = RoomTypeSerializer
    permission_classes = [IsAdminOrReadOnly] # Admin can CRUD, others can Read

class AmenityViewSet(viewsets.ModelViewSet):
    queryset = Amenity.objects.all()
    serializer_class = AmenitySerializer
    permission_classes = [IsAdminOrReadOnly] # Admin can CRUD, others can Read

class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all().select_related('room_type').prefetch_related('amenities')
    serializer_class = RoomSerializer
    # More granular permissions might be needed later, e.g. FrontDesk can change room status.
    permission_classes = [IsAdminOrReadOnly]

    # Example: Add filtering capabilities
    # filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # filterset_fields = ['room_type__id', 'status', 'floor', 'amenities__id'] # Use __id for foreign keys if filtering by ID
    # search_fields = ['room_number', 'room_type__name']
    # ordering_fields = ['price_per_night', 'room_number']
    # ordering = ['room_number'] # Default ordering

    # To enable filtering, you would:
    # 1. pip install django-filter
    # 2. Add 'django_filters' to INSTALLED_APPS in settings.py
    # 3. Uncomment the import for DjangoFilterBackend and filters
    # 4. Uncomment and configure the filter_backends, filterset_fields, etc.
    # Example query: /api/rooms/?status=AVAILABLE&room_type__id=1&ordering=price_per_night
    # Example query: /api/rooms/?search=101
    # Example query: /api/rooms/?amenities__id=2 (find rooms with amenity ID 2)
