from django.db import models # For Q objects
from rest_framework import viewsets, permissions
from .models import (
    RoomType, Amenity, Room, SeasonalPricing,
    RoomServiceRequest, CleaningAssignment # Added CleaningAssignment
)
from .serializers import (
    RoomTypeSerializer, AmenitySerializer, RoomSerializer,
    SeasonalPricingSerializer, RoomServiceRequestSerializer, CleaningAssignmentSerializer # Added CleaningAssignmentSerializer
)
from .permissions import CanManageSpecificRoomFields, IsAdminOrReadOnlyForRoomManagement
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
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

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'room_type__id': ['exact'],
        'status': ['exact', 'in'], # Enable filtering by status (exact match or list of statuses)
        'floor': ['exact', 'gte', 'lte'],
        'amenities__id': ['exact'] # Filter by rooms having a specific amenity
    }
    search_fields = ['room_number', 'room_type__name']
    ordering_fields = ['price_per_night', 'room_number', 'floor']
    ordering = ['room_number'] # Default ordering

    # To enable filtering, you would:
    # 1. pip install django-filter (already done)
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
            # Admin/FrontDesk can manage all.
            # Housekeeping can update status/assignment for non-maintenance.
            # Maintenance can update status/assignment for maintenance issues.
            if user.role == CustomUser.Role.ADMIN or user.role == CustomUser.Role.FRONT_DESK:
                return [permissions.IsAuthenticated()]
            if user.role == CustomUser.Role.HOUSEKEEPING:
                 # Allow update if not a maintenance issue or if they are assigned
                 # This needs object-level permission or check in perform_update for non-maintenance.
                return [permissions.IsAuthenticated()]
            if user.role == CustomUser.Role.MAINTENANCE:
                # Allow update only for MAINTENANCE_ISSUE types, ideally checked at object level.
                return [permissions.IsAuthenticated()]

        return [permissions.IsAdminUser()] # Default to Admin for safety

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        if not user.is_authenticated:
            return queryset.none()

        if user.role in [CustomUser.Role.ADMIN, CustomUser.Role.FRONT_DESK]:
            return queryset # Admin/FrontDesk can see all

        if user.role == CustomUser.Role.HOUSEKEEPING:
            # Housekeeping sees non-maintenance requests, or maintenance requests they are assigned to (unlikely).
            return queryset.filter(
                models.Q(request_type__in=[
                    RoomServiceRequest.RequestType.FOOD_BEVERAGE,
                    RoomServiceRequest.RequestType.TOILETRIES,
                    RoomServiceRequest.RequestType.OTHER
                ]) | models.Q(assigned_to=user)
            )

        if user.role == CustomUser.Role.MAINTENANCE:
            # Maintenance staff see only MAINTENANCE_ISSUE requests, ideally assigned to them or unassigned.
            return queryset.filter(
                models.Q(request_type=RoomServiceRequest.RequestType.MAINTENANCE_ISSUE) &
                (models.Q(assigned_to=user) | models.Q(assigned_to__isnull=True))
            )

        # If guest portal: filter by reservations linked to the guest's user account
        if hasattr(user, 'guest_profile') and user.guest_profile:
            return queryset.filter(reservation__guest=user.guest_profile, requested_by=user) # Guest sees requests they made for their reservations
        elif user.is_authenticated: # Authenticated non-staff, non-guest_profile user
            return queryset.filter(requested_by=user) # Can see requests they made

        return queryset.none()


    def perform_update(self, serializer):
        instance = serializer.instance
        original_status = instance.status
        new_status = serializer.validated_data.get('status', original_status)
        user = self.request.user

        # Permission checks for specific roles if not Admin/FrontDesk
        if user.role == CustomUser.Role.HOUSEKEEPING:
            if instance.request_type == RoomServiceRequest.RequestType.MAINTENANCE_ISSUE and instance.assigned_to != user:
                raise permissions.PermissionDenied("Housekeeping cannot update maintenance issues not assigned to them.")
            # Further checks can be added for which fields HK can update.

        if user.role == CustomUser.Role.MAINTENANCE:
            if instance.request_type != RoomServiceRequest.RequestType.MAINTENANCE_ISSUE:
                raise permissions.PermissionDenied("Maintenance staff can only update maintenance issues.")
            if instance.assigned_to != user and instance.assigned_to is not None: # Can take unassigned ones
                raise permissions.PermissionDenied("You can only update maintenance issues assigned to you or unassigned ones.")

        updated_instance = serializer.save()

        # Room status integration for MAINTENANCE_ISSUE
        if updated_instance.request_type == RoomServiceRequest.RequestType.MAINTENANCE_ISSUE:
            room = updated_instance.room
            if new_status == RoomServiceRequest.RequestStatus.IN_PROGRESS and \
               original_status != RoomServiceRequest.RequestStatus.IN_PROGRESS:
                # If a critical maintenance issue starts, room might go UNDER_MAINTENANCE
                # This depends on severity, which is not a field yet. For now, assume all IN_PROGRESS maintenance makes room U/M.
                if room.status != Room.RoomStatus.UNDER_MAINTENANCE:
                    room.status = Room.RoomStatus.UNDER_MAINTENANCE
                    room.save(update_fields=['status'])

            elif new_status == RoomServiceRequest.RequestStatus.COMPLETED and \
                 original_status != RoomServiceRequest.RequestStatus.COMPLETED:
                # If maintenance is completed, room might become AVAILABLE or NEEDS_CLEANING
                # This needs careful thought: does completing maintenance mean it's clean?
                # For now, assume it becomes AVAILABLE. A more robust system might set it to NEEDS_CLEANING first.
                if room.status == Room.RoomStatus.UNDER_MAINTENANCE: # Only change if it was U/M due to this
                    room.status = Room.RoomStatus.AVAILABLE
                    room.save(update_fields=['status'])

            elif new_status == RoomServiceRequest.RequestStatus.CANCELLED and \
                 original_status == RoomServiceRequest.RequestStatus.IN_PROGRESS and \
                 room.status == Room.RoomStatus.UNDER_MAINTENANCE:
                # If an IN_PROGRESS maintenance (that set room to U/M) is cancelled, room might revert.
                # This also needs care: was it U/M *only* due to this ticket?
                room.status = Room.RoomStatus.AVAILABLE # Or previous status if known
                room.save(update_fields=['status'])


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


class CleaningAssignmentViewSet(viewsets.ModelViewSet):
    queryset = CleaningAssignment.objects.all().select_related('room', 'assigned_to')
    serializer_class = CleaningAssignmentSerializer
    # filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    # filterset_fields = ['room__id', 'assigned_to__id', 'status']
    # search_fields = ['room__room_number', 'notes']

    def get_permissions(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return [permissions.IsAuthenticated()]

        if user.role == CustomUser.Role.ADMIN:
            return [permissions.IsAdminUser()]

        if user.role == CustomUser.Role.FRONT_DESK: # Front desk might view, or create for unassigned
            if self.action in ['list', 'retrieve', 'create']:
                return [permissions.IsAuthenticated()]

        if user.role == CustomUser.Role.HOUSEKEEPING:
            if self.action in ['list', 'retrieve']: # HK staff can see all or their own (filtered by queryset)
                return [permissions.IsAuthenticated()]
            if self.action in ['partial_update', 'update']: # HK staff can update their assignments
                return [permissions.IsAuthenticated()] # Further check in perform_update for ownership
            # HK staff should not create/delete assignments directly, only supervisors/admin.

        return [permissions.IsAdminUser()] # Default deny or admin only

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        if not user.is_authenticated:
            return queryset.none()

        if user.role in [CustomUser.Role.ADMIN, CustomUser.Role.FRONT_DESK]: # Admin/FrontDesk can see all.
            return queryset

        if user.role == CustomUser.Role.HOUSEKEEPING:
            # Housekeeping staff see only assignments assigned to them, or unassigned PENDING ones.
            return queryset.filter(
                models.Q(assigned_to=user) | models.Q(assigned_to__isnull=True, status=CleaningAssignment.AssignmentStatus.PENDING)
            )

        return queryset.none() # Other roles (e.g. Guest) see nothing

    def perform_update(self, serializer):
        user = self.request.user
        instance = serializer.instance

        # Housekeeping staff can only update status of their own assignments or claim unassigned PENDING ones.
        if user.role == CustomUser.Role.HOUSEKEEPING:
            if instance.assigned_to != user and instance.assigned_to is not None:
                raise permissions.PermissionDenied("You can only update your own cleaning assignments.")

            # Check if only allowed fields are being updated by HK staff (e.g., status, notes)
            allowed_hk_update_fields = {'status', 'notes'}
            for field in serializer.validated_data.keys():
                if field not in allowed_hk_update_fields:
                    raise permissions.PermissionDenied(f"Housekeeping staff cannot update field: {field}")

        # The signal handler auto_update_room_status_on_cleaning_completion will handle room status.
        serializer.save()

    def perform_create(self, serializer):
        # Admin or FrontDesk (acting as supervisor) can create and assign.
        # If created by HK staff (not allowed by default permissions above, but if it were),
        # it should not allow setting 'assigned_to' to someone else.
        # For now, only Admin/FrontDesk are expected here via permissions.
        serializer.save()
