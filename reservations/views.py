from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action # For custom actions
from django.utils import timezone

from .models import Guest, Reservation
from .serializers import GuestSerializer, ReservationSerializer
from hotel_core.models import Room # For room status updates

# Placeholder for role-based permissions - these would be defined in e.g. users/permissions.py
class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'ADMIN'

class IsFrontDesk(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'FRONT_DESK'

class IsGuestOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if isinstance(obj, Reservation):
            return obj.guest.user_account == request.user
        if isinstance(obj, Guest):
            return obj.user_account == request.user
        return False


class GuestViewSet(viewsets.ModelViewSet):
    queryset = Guest.objects.all()
    serializer_class = GuestSerializer

    def get_permissions(self):
        if self.action in ['list', 'destroy']:
            return [IsAdmin() or IsFrontDesk()]
        elif self.action in ['create', 'update', 'partial_update', 'retrieve']:
            # Admin/FrontDesk can manage any, Guest can manage their own if linked
            # This is a simplified version. A more robust way is IsAdminOrFrontDeskOrOwner
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Guest.objects.none()
        if user.role == 'ADMIN' or user.role == 'FRONT_DESK':
            return Guest.objects.all()
        # If user is a GUEST, they should only see their own profile
        # Assumes Guest model has a user_account link to CustomUser
        if hasattr(user, 'guest_profile'):
            return Guest.objects.filter(pk=user.guest_profile.pk)
        return Guest.objects.none()


class ReservationViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.all().select_related('guest', 'room', 'room__room_type').order_by('-created_at')
    serializer_class = ReservationSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'check_in', 'check_out', 'cancel']:
            return [IsAdmin() or IsFrontDesk()]
        elif self.action in ['list', 'retrieve']:
             # Allow Admin, FrontDesk to see all/any. Guest can see their own.
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Reservation.objects.none()

        if user.role == 'ADMIN' or user.role == 'FRONT_DESK':
            return Reservation.objects.all().select_related('guest', 'room', 'room__room_type').order_by('-created_at')

        # If user is GUEST, they should only see their own reservations
        if hasattr(user, 'guest_profile'):
             return Reservation.objects.filter(guest=user.guest_profile).select_related('guest', 'room', 'room__room_type').order_by('-created_at')
        return Reservation.objects.none()

    def perform_create(self, serializer):
        # Additional logic before saving, e.g., checking room availability again (though serializer does this)
        # serializer.validated_data['created_by'] = self.request.user # Example if tracking who made the reservation
        reservation = serializer.save()
        # Initial status is PENDING by model default. Room status change handled by check_in action.

    # Custom action for Check-in
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin or IsFrontDesk])
    def check_in(self, request, pk=None):
        reservation = self.get_object()
        if reservation.status == Reservation.ReservationStatus.CONFIRMED and reservation.check_in_date == timezone.now().date():
            reservation.status = Reservation.ReservationStatus.CHECKED_IN
            reservation.room.status = Room.RoomStatus.OCCUPIED
            reservation.save()
            reservation.room.save()
            return Response({'status': 'Reservation checked in successfully.'}, status=status.HTTP_200_OK)
        elif reservation.status != Reservation.ReservationStatus.CONFIRMED:
            return Response({'error': 'Reservation must be confirmed to check-in.'}, status=status.HTTP_400_BAD_REQUEST)
        elif reservation.check_in_date != timezone.now().date():
            return Response({'error': f'Check-in is only allowed on the check-in date ({reservation.check_in_date}).'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'error': 'Cannot check-in this reservation at this time.'}, status=status.HTTP_400_BAD_REQUEST)

    # Custom action for Check-out
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin or IsFrontDesk])
    def check_out(self, request, pk=None):
        reservation = self.get_object()
        if reservation.status == Reservation.ReservationStatus.CHECKED_IN:
            reservation.status = Reservation.ReservationStatus.CHECKED_OUT
            # In a real system, room status might go to NEEDS_CLEANING
            # For now, simplified to AVAILABLE if no other immediate bookings.
            # This needs a more robust check for overlapping/future bookings.
            reservation.room.status = Room.RoomStatus.NEEDS_CLEANING # More realistic
            reservation.save()
            reservation.room.save()
            # TODO: Trigger billing process here
            return Response({'status': 'Reservation checked out successfully.'}, status=status.HTTP_200_OK)
        return Response({'error': 'Reservation is not currently checked-in.'}, status=status.HTTP_400_BAD_REQUEST)

    # Custom action for Cancellation
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin or IsFrontDesk or IsGuestOwner]) # Guest can cancel their own
    def cancel(self, request, pk=None):
        reservation = self.get_object()
        # Add logic for cancellation policy, e.g., cannot cancel if too close to check_in_date or already checked_in
        if reservation.status in [Reservation.ReservationStatus.PENDING, Reservation.ReservationStatus.CONFIRMED]:
            old_room_status_if_occupied = reservation.room.status
            reservation.status = Reservation.ReservationStatus.CANCELLED
            reservation.save()

            # If room was marked occupied due to this reservation (e.g. if check-in was possible for PENDING in some flow)
            # or if a "BOOKED" status was used, this is where it would be reverted.
            # For now, assuming only CHECKED_IN sets room to OCCUPIED.
            # If this cancellation makes the room available:
            # This check needs to be robust, ensuring no other CONFIRMED/CHECKED_IN reservation exists for the room.
            # For simplicity here, we assume if this was the only one, room becomes available.
            # A better check:
            # is_room_still_booked = Reservation.objects.filter(
            # room=reservation.room,
            # status__in=[Reservation.ReservationStatus.CONFIRMED, Reservation.ReservationStatus.CHECKED_IN],
            # check_in_date__lt=reservation.check_out_date, # Consider current and future bookings
            # check_out_date__gt=reservation.check_in_date
            # ).exclude(pk=reservation.pk).exists()
            # if not is_room_still_booked and old_room_status_if_occupied == Room.RoomStatus.OCCUPIED:
            # reservation.room.status = Room.RoomStatus.AVAILABLE
            # reservation.room.save()
            # For now, the room status is primarily handled by check-in/check-out.
            # Cancellation of a CONFIRMED reservation means it won't proceed to CHECKED_IN.

            return Response({'status': 'Reservation cancelled successfully.'}, status=status.HTTP_200_OK)
        return Response({'error': 'This reservation cannot be cancelled at its current state.'}, status=status.HTTP_400_BAD_REQUEST)

    def perform_destroy(self, instance):
        # Similar to cancellation, ensure room status is handled if necessary.
        # Generally, direct deletion of reservations might be restricted; cancellation is preferred.
        room = instance.room
        is_room_occupied_by_this = (instance.status == Reservation.ReservationStatus.CHECKED_IN and room.status == Room.RoomStatus.OCCUPIED)

        super().perform_destroy(instance)

        if is_room_occupied_by_this:
            # Check if any other active (Confirmed or Checked-In) reservations exist for this room currently.
            # This is a simplified check.
            if not Reservation.objects.filter(
                room=room,
                status__in=[Reservation.ReservationStatus.CHECKED_IN] # Only current check-ins matter for immediate occupancy
            ).exists():
                # A more robust check would consider if other confirmed bookings for *today* exist.
                room.status = Room.RoomStatus.AVAILABLE # Or NEEDS_CLEANING
                room.save()
