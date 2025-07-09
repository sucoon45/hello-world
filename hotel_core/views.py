from rest_framework import viewsets, permissions
from .models import RoomType, Amenity, Room, SeasonalPricing, RoomServiceRequest # Added RoomServiceRequest
from .serializers import (
    RoomTypeSerializer, AmenitySerializer, RoomSerializer,
    SeasonalPricingSerializer, RoomServiceRequestSerializer # Added RoomServiceRequestSerializer
)
from .permissions import CanManageSpecificRoomFields, IsAdminOrReadOnlyForRoomManagement
# from django_filters.rest_framework import DjangoFilterBackend
# from rest_framework import filters
from users.models import CustomUser # For permission checks
from reservations.models import Reservation # For RoomServiceRequest logic


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
    permission_classes = [IsAdminOrReadOnlyForRoomManagement] # Use the more specific Admin-only for writes

class AmenityViewSet(viewsets.ModelViewSet):
    queryset = Amenity.objects.all()
    serializer_class = AmenitySerializer
    permission_classes = [IsAdminOrReadOnlyForRoomManagement] # Use the more specific Admin-only for writes

class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all().select_related('room_type').prefetch_related('amenities')
    serializer_class = RoomSerializer
    permission_classes = [CanManageSpecificRoomFields] # Apply the new role-based permission

    # If using CanManageSpecificRoomFields, the serializer needs to be smart
    # about what fields non-admins can update.
    # For example, ensure FrontDesk/Housekeeping can *only* update 'status' and maybe a few other fields.
    # This can be done by overriding `get_serializer_class` or `perform_update`.
    # Or, the serializer's `update` method itself can check user role.

    # A simpler way if CanManageSpecificRoomFields allows general updates by FD/HK:
    # The RoomSerializer currently makes all fields (except read_only ones) writable.
    # We might need a different serializer for updates by FD/HK if they should only update status.
    # For now, assuming they can update any non-read-only field on Room if they have PATCH permission.
    # The `status` field is not in RoomSerializer's read_only_fields, so it's writable.

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


class SeasonalPricingViewSet(viewsets.ModelViewSet):
    queryset = SeasonalPricing.objects.all().select_related('room_type')
    serializer_class = SeasonalPricingSerializer
    permission_classes = [permissions.IsAdminUser] # Only admins can manage pricing rules

    # Add filtering for room_type if needed
    # filterset_fields = ['room_type__id', 'name']


class RoomServiceRequestViewSet(viewsets.ModelViewSet):
    queryset = RoomServiceRequest.objects.all().select_related(
        'room', 'reservation', 'requested_by', 'assigned_to'
    )
    serializer_class = RoomServiceRequestSerializer
    # Define permissions - e.g. IsAuthenticated for base, then more granular per action or user role.
    # filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # filterset_fields = ['room__id', 'status', 'request_type', 'assigned_to__id']
    # search_fields = ['description', 'room__room_number']
    # ordering_fields = ['requested_at', 'completed_at', 'price']


    def get_permissions(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return [permissions.IsAuthenticated()] # Deny all

        if view.action == 'create':
            # Guests (if they have a linked reservation/room) or Staff can create.
            # This needs refinement if guests are to create directly.
            # For now, let's assume staff (Admin/FrontDesk) create.
            if user.role in [CustomUser.Role.ADMIN, CustomUser.Role.FRONT_DESK]:
                return [permissions.IsAuthenticated()]
            # else: # Guest creation logic would go here
            #     return [permissions.IsAuthenticated()] # And check ownership in perform_create

        if view.action in ['list', 'retrieve']:
            # Staff can list/retrieve all. Guests can list/retrieve their own (linked to their reservations).
            return [permissions.IsAuthenticated()]

        if view.action in ['update', 'partial_update', 'destroy']:
            # Only staff can modify/delete. Specific roles might be for specific fields.
            if user.role in [CustomUser.Role.ADMIN, CustomUser.Role.FRONT_DESK, CustomUser.Role.HOUSEKEEPING]: # Housekeeping might update status/assignment
                return [permissions.IsAuthenticated()]

        return [permissions.IsAdminUser()] # Default to Admin for safety

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        if not user.is_authenticated:
            return queryset.none()

        if user.role in [CustomUser.Role.ADMIN, CustomUser.Role.FRONT_DESK, CustomUser.Role.HOUSEKEEPING]:
            return queryset # Staff can see all

        # If guest portal: filter by reservations linked to the guest's user account
        # This requires CustomUser to be linked to Guest, and Guest to Reservation.
        if hasattr(user, 'guest_profile') and user.guest_profile:
            return queryset.filter(reservation__guest=user.guest_profile)
        elif user.is_authenticated: # Authenticated non-staff, non-guest_profile user (e.g. other staff roles not listed)
            return queryset.filter(requested_by=user) # Can see requests they made

        return queryset.none()


    def perform_create(self, serializer):
        # Automatically set 'requested_by' to the current user.
        # If the user is a GUEST and creating for their own reservation,
        # ensure the reservation belongs to them.
        user = self.request.user
        reservation = serializer.validated_data.get('reservation')
        room = serializer.validated_data.get('room')

        if user.role == CustomUser.Role.GUEST:
            if not hasattr(user, 'guest_profile'):
                raise permissions.PermissionDenied("Guest profile not found for this user.")

            # If reservation is provided, it must belong to the guest.
            if reservation and reservation.guest != user.guest_profile:
                raise permissions.PermissionDenied("You can only create service requests for your own reservations.")

            # If no reservation, but room is provided, ensure room is part of an active reservation for the guest.
            # This logic can be complex if allowing requests without a specific reservation ID.
            # For now, if guest creates, assume reservation_id is provided and validated above.
            # Or, if only room_id is provided by guest, we'd need to find their current reservation for that room.
            if not reservation and room:
                 # Try to find an active reservation for this guest in this room
                active_guest_reservation_for_room = Reservation.objects.filter(
                    guest=user.guest_profile,
                    room=room,
                    status=Reservation.ReservationStatus.CHECKED_IN
                ).first()
                if not active_guest_reservation_for_room:
                    raise permissions.PermissionDenied("You must have an active checked-in reservation for this room to request service, or provide your reservation ID.")
                serializer.validated_data['reservation'] = active_guest_reservation_for_room


        serializer.save(requested_by=self.request.user)
