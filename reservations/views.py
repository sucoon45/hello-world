import uuid # For generating group identifier
from decimal import Decimal, InvalidOperation # For fee validation
from django.db import transaction # For atomic group creation
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
# For filtering
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters


from .models import Guest, Reservation, GuestDocument
from .serializers import GuestSerializer, ReservationSerializer, GuestDocumentSerializer
from .email_utils import send_reservation_confirmation_email, send_reservation_cancellation_email
from hotel_core.models import Room # For room status updates
from users.models import CustomUser # For checking user role in GuestDocumentViewSet
from billing.services import generate_invoice_for_reservation # For invoice generation

# Placeholder for role-based permissions - these would be defined in e.g. users/permissions.py
class IsAdmin(permissions.BasePermission): # Example placeholder
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
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'status': ['exact', 'in'],
        'check_in_date': ['exact', 'gte', 'lte'],
        'check_out_date': ['exact', 'gte', 'lte'],
        'room__id': ['exact'],
        'room__room_type__id': ['exact'],
        'guest__id': ['exact'],
        'group_name': ['exact', 'icontains'],
        'group_identifier': ['exact'],
    }
    search_fields = ['guest__first_name', 'guest__last_name', 'guest__email', 'room__room_number', 'group_name']
    ordering_fields = ['check_in_date', 'created_at', 'total_price']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'check_in', 'check_out', 'cancel', 'create_group_booking']:
            return [IsAdmin() or IsFrontDesk()] # Assuming IsAdmin and IsFrontDesk are properly defined
        elif self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Reservation.objects.none()

        # Admins or Front Desk can see all reservations based on filters
        if user.role in ['ADMIN', 'FRONT_DESK']:
            return Reservation.objects.all().select_related('guest', 'room', 'room__room_type').order_by('-created_at')

        # Guests can see their own reservations
        # This assumes guest_profile is correctly linked to the user
        if hasattr(user, 'guest_profile') and user.guest_profile:
            return Reservation.objects.filter(guest=user.guest_profile).select_related('guest', 'room', 'room__room_type').order_by('-created_at')

        return Reservation.objects.none()

    def create(self, request, *args, **kwargs):
        """
        Overrides the default create method to handle:
        1. Single reservation creation (standard DRF behavior).
        2. Group reservation creation if request.data is a list of reservation objects.
           - Expects a 'group_name' at the top level of the request or in each item.
           - A common 'group_identifier' will be generated and assigned.
        """
        is_many = isinstance(request.data, list)

        if not is_many: # Standard single reservation creation
            return super().create(request, *args, **kwargs)

        # Handling group (list) reservation creation
        group_name_from_request = request.query_params.get('group_name', None) # Or pass in body
        group_identifier = uuid.uuid4()

        created_reservations_data = []
        errors = []

        with transaction.atomic(): # Ensure all or no reservations are created for the group
            for index, res_data in enumerate(request.data):
                # Ensure each reservation in the group has the group identifier and name
                res_data['group_identifier'] = group_identifier
                if group_name_from_request and 'group_name' not in res_data:
                    res_data['group_name'] = group_name_from_request
                elif 'group_name' not in res_data and not group_name_from_request:
                     errors.append({f"item_{index}": {"group_name": "Group name is required for group bookings."}})
                     continue


                serializer = self.get_serializer(data=res_data)
                if serializer.is_valid():
                    try:
                        # Manually set group_identifier before saving, as it's read-only in serializer
                        # The serializer's save() method won't pick it up from validated_data if read_only=True
                        # So, we pass it directly to save() if the model field isn't editable=False
                        # Since our model field `group_identifier` is `editable=False`, we should pass it to save()
                        self.perform_create(serializer, group_identifier=group_identifier, group_name=res_data.get('group_name'))
                        created_reservations_data.append(serializer.data)
                    except Exception as e: # Catch any validation error from perform_create or save
                        errors.append({f"item_{index}": str(e)})
                else:
                    errors.append({f"item_{index}": serializer.errors})

            if errors:
                transaction.set_rollback(True) # Rollback transaction due to errors
                return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        return Response(created_reservations_data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer, group_identifier=None, group_name=None):
        # If it's a group booking, the identifier and name are passed from the overridden create method
        if group_identifier and group_name:
            serializer.save(group_identifier=group_identifier, group_name=group_name)
        else: # Single reservation
            # If group_name is provided for a single reservation, generate a new group_identifier
            # Or, one might decide single reservations cannot initiate groups this way without a specific flag.
            # For now, if group_name is present, we treat it as a group of one.
            current_group_name = serializer.validated_data.get('group_name')
            if current_group_name and not serializer.validated_data.get('group_identifier'):
                 serializer.save(group_identifier=uuid.uuid4()) # New group for this single reservation
            else:
                 serializer.save()

        # Send confirmation email if status is set to CONFIRMED during creation
        # This depends on whether reservations can be created directly as CONFIRMED
        # or if they always start as PENDING and then updated.
        # If they can be created as CONFIRMED:
        if serializer.instance.status == Reservation.ReservationStatus.CONFIRMED:
            send_reservation_confirmation_email(serializer.instance)
        # Initial status is PENDING by model default. Room status change handled by check_in action.

    def perform_update(self, serializer):
        original_status = serializer.instance.status # Get status before update
        updated_reservation = serializer.save() # This saves the changes

        # Check if status changed to CONFIRMED
        if original_status != Reservation.ReservationStatus.CONFIRMED and \
           updated_reservation.status == Reservation.ReservationStatus.CONFIRMED:
            send_reservation_confirmation_email(updated_reservation)
            # Update room status to BOOKED if it's currently AVAILABLE
            if updated_reservation.room.status == Room.RoomStatus.AVAILABLE:
                updated_reservation.room.status = Room.RoomStatus.BOOKED
                updated_reservation.room.save(update_fields=['status'])

        # Handle other status changes if necessary, e.g. if a reservation is
        # moved from CONFIRMED back to PENDING.
        # For example, if reservation becomes PENDING or CANCELLED from CONFIRMED/CHECKED_IN:
        if original_status in [Reservation.ReservationStatus.CONFIRMED, Reservation.ReservationStatus.CHECKED_IN] and \
           updated_reservation.status in [Reservation.ReservationStatus.PENDING, Reservation.ReservationStatus.CANCELLED]:
            # This logic is complex because multiple reservations might affect room status.
            # The `cancel` action has more specific logic.
            # Generally, if a confirmed/checked-in reservation is voided, the room might become available
            # or revert to BOOKED if other confirmed bookings exist.
            # For now, specific transitions are handled in check_in, check_out, cancel actions.
            pass


    # Custom action for Check-in
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin]) # Placeholder: Replace IsAdmin with actual permission class for Admin/FrontDesk
    def check_in(self, request, pk=None):
        reservation = self.get_object()
        room = reservation.room

        if reservation.status == Reservation.ReservationStatus.CHECKED_IN:
            # If already checked-in, idempotent success
            serializer = self.get_serializer(reservation)
            return Response(serializer.data, status=status.HTTP_200_OK)

        if reservation.status != Reservation.ReservationStatus.CONFIRMED:
            return Response({'error': 'Reservation must be confirmed to check-in.'}, status=status.HTTP_400_BAD_REQUEST)

        # Standard check-in day is today or in the past (for late check-ins)
        is_early_check_in_scenario = False
        if reservation.check_in_date > timezone.now().date(): # Trying to check-in before the actual check_in_date
            if reservation.is_early_check_in_approved and reservation.requested_early_check_in and reservation.requested_early_check_in.date() == timezone.now().date():
                # Approved for today, and it is today. Check time if needed (e.g. hotel policy for earliest possible early check-in)
                is_early_check_in_scenario = True # Potentially allow based on time
            else:
                return Response({'error': f'Check-in is for a future date ({reservation.check_in_date}). Early check-in not approved for today.'}, status=status.HTTP_400_BAD_REQUEST)
        elif reservation.check_in_date == timezone.now().date(): # Checking in on the reservation date
            # If requested_early_check_in time is set and approved, and current time is before standard check-in
            standard_check_in_time = datetime.time(15,0) # Hotel's standard check-in time, e.g., 3 PM. Should be a setting.
            if reservation.is_early_check_in_approved and reservation.requested_early_check_in and \
               timezone.now().time() < reservation.requested_early_check_in.time() and \
               timezone.now().time() < standard_check_in_time : # Trying to check-in earlier than approved early time or standard time
                 # This logic might need refinement: if approved for 10 AM, can check in at 10 AM or later.
                 # If current time is before requested_early_check_in.time(), it's too early even for approved.
                 # This part handles checking in *before* the standard check-in time on the check-in day.
                 is_early_check_in_scenario = True # Falls into early check-in if before standard time and approved
            elif timezone.now().time() < standard_check_in_time and not reservation.is_early_check_in_approved:
                 return Response({'error': f'Standard check-in time is {standard_check_in_time.strftime("%H:%M")}. Early check-in requires approval.'}, status=status.HTTP_400_BAD_REQUEST)


        # Check room status (moved down to allow early check-in validation first)
        if room.status == Room.RoomStatus.UNDER_MAINTENANCE:
             return Response({'error': f'Room {room.room_number} is under maintenance and cannot be checked-in.'}, status=status.HTTP_400_BAD_REQUEST)

        # If room is OCCUPIED, it's an error unless it's occupied by this reservation (which is not yet checked in, so this is a conflict)
        if room.status == Room.RoomStatus.OCCUPIED:
             return Response({'error': f'Room {room.room_number} is already occupied.'}, status=status.HTTP_409_CONFLICT) # Conflict

        # If room NEEDS_CLEANING, only Admin/FrontDesk might override (e.g. guest agrees)
        # This override logic is not implemented here, just basic restriction.
        if room.status == Room.RoomStatus.NEEDS_CLEANING and not (request.user.role in ['ADMIN', 'FRONT_DESK']):
             return Response({'error': f'Room {room.room_number} needs cleaning before check-in.'}, status=status.HTTP_400_BAD_REQUEST)

        # Proceed with check-in
        reservation.status = Reservation.ReservationStatus.CHECKED_IN
        room.status = Room.RoomStatus.OCCUPIED

        with transaction.atomic():
            reservation.save(update_fields=['status'])
            room.save(update_fields=['status'])

        serializer = self.get_serializer(reservation)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Custom action for Check-out
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin]) # Placeholder: Replace IsAdmin with actual permission class for Admin/FrontDesk
    def check_out(self, request, pk=None):
        reservation = self.get_object()
        room = reservation.room

        if reservation.status == Reservation.ReservationStatus.CHECKED_OUT:
            # If already checked-out, idempotent success
            serializer = self.get_serializer(reservation)
            return Response(serializer.data, status=status.HTTP_200_OK)

        if reservation.status != Reservation.ReservationStatus.CHECKED_IN:
            return Response({'error': 'Reservation is not currently checked-in.'}, status=status.HTTP_400_BAD_REQUEST)

        # Late check-out logic
        standard_check_out_time = datetime.time(11,0) # Hotel's standard check-out time, e.g., 11 AM. Should be a setting.
        current_time = timezone.now().time()
        current_date = timezone.now().date()

        is_late_checkout_scenario = False
        if current_date == reservation.check_out_date and current_time > standard_check_out_time:
            is_late_checkout_scenario = True
        elif current_date > reservation.check_out_date: # Checking out on a day after scheduled
            is_late_checkout_scenario = True

        if is_late_checkout_scenario and not reservation.is_late_check_out_approved:
            # If past standard check-out time/day without approval, this is an issue.
            # For now, we'll allow the API call to proceed to mark as CHECKED_OUT,
            # but a real system might flag this for extra charges or manager attention.
            # The system won't prevent check-out here, but notes it's a late one without approval.
            pass # Log this event or handle as per hotel policy.

        if is_late_checkout_scenario and reservation.is_late_check_out_approved and reservation.requested_late_check_out:
            if timezone.now() > reservation.requested_late_check_out:
                # Guest is checking out even later than their approved late check-out time.
                # Flag for potential additional fees.
                pass # Log this event.

        reservation.status = Reservation.ReservationStatus.CHECKED_OUT
        room.status = Room.RoomStatus.NEEDS_CLEANING # Standard procedure after checkout

        with transaction.atomic():
            reservation.save(update_fields=['status'])
            room.save(update_fields=['status'])

        # Trigger invoice generation
        try:
            invoice = generate_invoice_for_reservation(reservation)
            # Optionally, include some invoice info in the response
            response_data = self.get_serializer(reservation).data
            response_data['invoice_id'] = invoice.id
            response_data['invoice_number'] = invoice.invoice_number
            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            # Log the error e
            print(f"Error generating invoice for reservation {reservation.id}: {e}")
            # Return success for check-out but indicate invoice issue
            return Response({
                "status": "Reservation checked out successfully, but invoice generation failed.",
                "reservation_data": self.get_serializer(reservation).data,
                "invoice_error": str(e)
            }, status=status.HTTP_207_MULTI_STATUS)


    # Custom action for Cancellation
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated]) # More granular: IsAdmin or IsFrontDesk or IsOwner
    def cancel(self, request, pk=None):
        reservation = self.get_object()
        user = request.user

        # Check if user is staff (Admin/FrontDesk) or guest owner
        can_cancel = False
        if user.is_authenticated:
            if user.role in ['ADMIN', 'FRONT_DESK']:
                can_cancel = True
            elif hasattr(user, 'guest_profile') and user.guest_profile == reservation.guest:
                 # Add logic for cancellation policy for guests, e.g., cannot cancel if too close to check_in_date
                if reservation.status in [Reservation.ReservationStatus.PENDING, Reservation.ReservationStatus.CONFIRMED]:
                     # Example policy: Guest can cancel up to 1 day before check-in
                    if reservation.check_in_date >= (timezone.now().date() + timezone.timedelta(days=1)):
                        can_cancel = True
                    else:
                        # Specific error if guest is too late to cancel
                        return Response({'error': 'Cancellation window closed. Contact support.'}, status=status.HTTP_400_BAD_REQUEST)
                else: # Guest trying to cancel a reservation not in PENDING or CONFIRMED state
                    return Response({'error': 'Reservation cannot be cancelled at its current state by guest.'}, status=status.HTTP_400_BAD_REQUEST)


        if not can_cancel:
            return Response({'error': 'You do not have permission to cancel this reservation or it cannot be cancelled now.'}, status=status.HTTP_403_FORBIDDEN)

        # Add logic for cancellation policy, e.g., cannot cancel if too close to check_in_date or already checked_in
        if reservation.status in [Reservation.ReservationStatus.PENDING, Reservation.ReservationStatus.CONFIRMED]:
            room_to_update = reservation.room
            original_reservation_status = reservation.status

            reservation.status = Reservation.ReservationStatus.CANCELLED

            with transaction.atomic():
                reservation.save(update_fields=['status'])

                # If the room was BOOKED specifically for this CONFIRMED reservation,
                # and no other CONFIRMED or CHECKED_IN reservations exist for this room for an overlapping period,
                # set room to AVAILABLE.
                if original_reservation_status == Reservation.ReservationStatus.CONFIRMED and \
                   room_to_update.status == Room.RoomStatus.BOOKED:

                    # Check for other Confirmed/CheckedIn reservations for this room that might keep it BOOKED/OCCUPIED
                    # This needs to check for any current or future bookings for the room.
                    # A simplified check: if any other CONFIRMED reservation exists for this room,
                    # it might remain BOOKED. If not, it becomes AVAILABLE.
                    # This doesn't consider date overlaps perfectly, a full availability check for the room is better.
                    other_confirmed_or_checkedin_reservations = Reservation.objects.filter(
                        room=room_to_update,
                        status__in=[Reservation.ReservationStatus.CONFIRMED, Reservation.ReservationStatus.CHECKED_IN]
                    ).exclude(pk=reservation.pk).exists()

                    if not other_confirmed_or_checkedin_reservations:
                        room_to_update.status = Room.RoomStatus.AVAILABLE
                        room_to_update.save(update_fields=['status'])
                    # Else: Room remains BOOKED or OCCUPIED due to other reservations.

            send_reservation_cancellation_email(reservation) # Send cancellation email
            return Response({'status': 'Reservation cancelled successfully.'}, status=status.HTTP_200_OK)

        elif reservation.status == Reservation.ReservationStatus.CANCELLED:
            return Response({'status': 'Reservation is already cancelled.'}, status=status.HTTP_200_OK)
        else: # e.g. CHECKED_IN, CHECKED_OUT, NO_SHOW
            return Response({'error': f'Reservation in {reservation.get_status_display()} state cannot be cancelled via this action.'}, status=status.HTTP_400_BAD_REQUEST)

    def perform_destroy(self, instance):
        # Similar to cancellation, ensure room status is handled if necessary.
        # Generally, direct deletion of reservations might be restricted; cancellation is preferred.
        room = instance.room
        original_reservation_status = instance.status
        original_room_status = room.status

        super().perform_destroy(instance) # Reservation is now deleted

        # Logic to update room status after deleting a reservation.
        # This needs to be robust and consider other existing bookings for the room.

        # If the deleted reservation was CHECKED_IN:
        if original_reservation_status == Reservation.ReservationStatus.CHECKED_IN:
            # Check if any other reservation is currently CHECKED_IN for this room (should not happen in a correct system).
            # If not, room becomes NEEDS_CLEANING.
            if not Reservation.objects.filter(room=room, status=Reservation.ReservationStatus.CHECKED_IN).exists():
                room.status = Room.RoomStatus.NEEDS_CLEANING
                room.save(update_fields=['status'])
            # If (somehow) another reservation is CHECKED_IN, room remains OCCUPIED (data integrity issue elsewhere).

        # If the deleted reservation was CONFIRMED and room was BOOKED:
        elif original_reservation_status == Reservation.ReservationStatus.CONFIRMED and \
             original_room_status == Room.RoomStatus.BOOKED:
            # Check if other CONFIRMED or CHECKED_IN reservations exist for this room.
            # If not, room becomes AVAILABLE.
            if not Reservation.objects.filter(
                room=room,
                status__in=[Reservation.ReservationStatus.CONFIRMED, Reservation.ReservationStatus.CHECKED_IN]
            ).exists():
                room.status = Room.RoomStatus.AVAILABLE
                room.save(update_fields=['status'])
            # Else, room might remain BOOKED or become OCCUPIED based on other reservations.
            # The status would effectively be determined by the next chronological CONFIRMED/CHECKED_IN booking.
            # This simplified logic doesn't re-evaluate to set it to BOOKED by another reservation.
            # A full re-evaluation of room status based on all its reservations would be more robust here.

        # Other cases (e.g., deleting a PENDING reservation) usually don't change room status if it was AVAILABLE.

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin], url_path='change-room') # Placeholder for Admin/FrontDesk
    def change_room(self, request, pk=None):
        reservation = self.get_object()
        new_room_id = request.data.get('new_room_id')

        if not new_room_id:
            return Response({"error": "new_room_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            new_room = Room.objects.select_related('room_type').get(pk=new_room_id)
        except Room.DoesNotExist:
            return Response({"error": "New room not found."}, status=status.HTTP_404_NOT_FOUND)

        # 1. Check reservation status
        if reservation.status not in [Reservation.ReservationStatus.PENDING, Reservation.ReservationStatus.CONFIRMED]:
            return Response({"error": f"Cannot change room for a reservation with status '{reservation.status}'."}, status=status.HTTP_400_BAD_REQUEST)

        if reservation.room == new_room:
            return Response({"message": "Reservation is already assigned to this room."}, status=status.HTTP_200_OK)

        # 2. Check room type compatibility (optional, based on policy)
        # For now, let's assume any room change must be to the same type or needs explicit handling for upgrades/downgrades.
        # This example enforces same room type.
        if reservation.room.room_type != new_room.room_type:
            # A more complex system could allow this with price adjustments.
            return Response({"error": f"New room must be of the same type ({reservation.room.room_type.name}). "
                                      f"Selected room is type {new_room.room_type.name}."},
                            status=status.HTTP_400_BAD_REQUEST)

        # 3. Check new room availability (using similar logic from ReservationSerializer.validate)
        # Ensure new_room is not UNDER_MAINTENANCE etc.
        if new_room.status == Room.RoomStatus.UNDER_MAINTENANCE:
             return Response({"error": f"New room {new_room.room_number} is under maintenance."}, status=status.HTTP_400_BAD_REQUEST)

        conflicting_statuses = [Reservation.ReservationStatus.CONFIRMED, Reservation.ReservationStatus.CHECKED_IN]
        overlapping_reservations = Reservation.objects.filter(
            room=new_room,
            status__in=conflicting_statuses,
            check_in_date__lt=reservation.check_out_date,
            check_out_date__gt=reservation.check_in_date
        ).exclude(pk=reservation.pk) # Exclude current reservation if it was somehow already linked to new_room (shouldn't be)

        if overlapping_reservations.exists():
            return Response(
                {"error": f"New room {new_room.room_number} is not available for the reservation dates due to an existing booking."},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_room = reservation.room

        with transaction.atomic():
            reservation.room = new_room
            reservation.save(update_fields=['room']) # This will also trigger total_price recalc if fees are involved.

            # Update status of the new room
            if new_room.status == Room.RoomStatus.AVAILABLE:
                new_room.status = Room.RoomStatus.BOOKED if reservation.status == Reservation.ReservationStatus.CONFIRMED else new_room.status # Or PENDING_ASSIGNMENT?
                new_room.save(update_fields=['status'])

            # Update status of the old room
            # If old_room was BOOKED by this reservation, it might become AVAILABLE
            if old_room.status == Room.RoomStatus.BOOKED:
                # Check if any other CONFIRMED/CHECKED_IN reservations exist for the old_room
                if not Reservation.objects.filter(
                    room=old_room,
                    status__in=[Reservation.ReservationStatus.CONFIRMED, Reservation.ReservationStatus.CHECKED_IN]
                    ).exclude(pk=reservation.pk).exists(): # Exclude the current reservation which is being moved
                    old_room.status = Room.RoomStatus.AVAILABLE
                    old_room.save(update_fields=['status'])

        serializer = self.get_serializer(reservation)
        return Response(serializer.data, status=status.HTTP_200_OK)


    @action(detail=True, methods=['patch'], permission_classes=[IsAdmin], url_path='manage-special-requests') # Placeholder for Admin/FrontDesk permission
    def manage_special_requests(self, request, pk=None): # pragma: no cover
        reservation = self.get_object()

        # Fields that can be updated by this action
        allowed_fields = {
            'is_early_check_in_approved', 'early_check_in_fee',
            'is_late_check_out_approved', 'late_check_out_fee'
        }

        data_to_update = {}
        has_updates = False
        for field in allowed_fields:
            if field in request.data:
                data_to_update[field] = request.data[field]
                has_updates = True

        if not has_updates:
            return Response({"error": "No valid fields provided for update."}, status=status.HTTP_400_BAD_REQUEST)

        # Use serializer for validation and partial update
        # Pass only the fields that are allowed to be updated by this action.
        # instance=reservation, data=data_to_update, partial=True
        # However, the main ReservationSerializer has these as read_only for general users.
        # For staff updates, we can bypass read_only or use a different serializer.
        # Direct update for simplicity here, assuming staff provides valid data.

        updated_fields_list = []
        for field, value in data_to_update.items():
            # Basic validation can be added here, e.g. fee is positive number
            if field.endswith('_fee') and value is not None:
                try:
                    value = Decimal(value)
                    if value < 0:
                        return Response({field: "Fee cannot be negative."}, status=status.HTTP_400_BAD_REQUEST)
                except InvalidOperation:
                    return Response({field: "Invalid fee amount."}, status=status.HTTP_400_BAD_REQUEST)

            setattr(reservation, field, value)
            updated_fields_list.append(field)

        if updated_fields_list:
            # The save() method on Reservation will automatically recalculate total_price
            reservation.save()
            serializer = self.get_serializer(reservation)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            # Should not happen if has_updates was true, but as a safeguard.
            return Response({"detail": "No changes made."}, status=status.HTTP_200_OK) # pragma: no cover


class GuestDocumentViewSet(viewsets.ModelViewSet):
    queryset = GuestDocument.objects.all()
    serializer_class = GuestDocumentSerializer
    # parser_classes = [MultiPartParser, FormParser] # For file uploads

    def get_permissions(self):
        # Allow Admin/FrontDesk to do anything.
        # Guest can create (upload) and list/retrieve their own documents.
        user = self.request.user
        if not user.is_authenticated:
            return [permissions.IsAuthenticated()] # Deny by default

        if user.role in ['ADMIN', 'FRONT_DESK']:
            return [permissions.IsAuthenticated()] # Or IsAdminUser/IsFrontDeskUser

        # Guest permissions
        if self.action in ['create', 'list', 'retrieve']:
             # For list/retrieve, queryset filtering will handle ownership.
             # For create, guest_id in request data should match user's guest profile.
            return [permissions.IsAuthenticated()]

        return [IsAdmin()] # Default to admin for other actions like destroy/update by staff

    def get_queryset(self):
        """
        This method should return a list of documents
        for the currently authenticated user if they are a guest,
        or all documents for staff, or documents for a specific guest if guest_pk is in URL.
        """
        user = self.request.user
        guest_pk = self.kwargs.get('guest_pk') # From nested URL: /guests/{guest_pk}/documents/

        if user.role in ['ADMIN', 'FRONT_DESK']:
            if guest_pk:
                return GuestDocument.objects.filter(guest_id=guest_pk).select_related('guest', 'verified_by')
            return GuestDocument.objects.all().select_related('guest', 'verified_by') # Staff can see all if not nested

        # If user is a guest, they can only see their own documents.
        # This requires the guest_pk from URL to match their own guest profile.
        if hasattr(user, 'guest_profile') and user.guest_profile:
            if guest_pk and str(user.guest_profile.pk) == str(guest_pk): # Ensure accessing own documents via nested URL
                 return GuestDocument.objects.filter(guest=user.guest_profile).select_related('guest', 'verified_by')
            elif not guest_pk: # Non-nested access, show own documents
                 return GuestDocument.objects.filter(guest=user.guest_profile).select_related('guest', 'verified_by')

        return GuestDocument.objects.none()


    def perform_create(self, serializer):
        # When creating via nested URL /guests/{guest_pk}/documents/, guest_pk is available.
        # The serializer's guest_id field will use this.
        guest_pk = self.kwargs.get('guest_pk')
        guest = None
        if guest_pk:
            try:
                guest = Guest.objects.get(pk=guest_pk)
            except Guest.DoesNotExist:
                raise serializers.ValidationError({"guest_id": "Invalid Guest ID in URL."})

        # Security check: if user is a GUEST, ensure they are uploading to their own profile.
        user = self.request.user
        if user.role == CustomUser.Role.GUEST:
            if not hasattr(user, 'guest_profile') or (guest and user.guest_profile != guest):
                raise permissions.PermissionDenied("You can only upload documents for your own guest profile.")
            # If guest_id was not in request body but guest_pk in URL, use it.
            if guest and 'guest_id' not in serializer.validated_data: # Should be handled by serializer's source='guest'
                 serializer.save(guest=user.guest_profile)
                 return

        # If guest_id is part of the payload (and validated by serializer), it's used.
        # If guest_pk in URL, serializer's guest_id field (source='guest') should handle it.
        # If serializer needs guest explicitly:
        if guest and not serializer.validated_data.get('guest'):
             serializer.save(guest=guest)
        else:
             serializer.save()


    @action(detail=True, methods=['post'], permission_classes=[IsAdmin], url_path='verify') # Placeholder for Admin/FrontDesk
    def verify_document(self, request, pk=None, guest_pk=None): # guest_pk from nested router
        document = self.get_object()
        if document.verified_at:
            return Response({"message": "Document already verified."}, status=status.HTTP_400_BAD_REQUEST)

        document.verified_at = timezone.now()
        document.verified_by = request.user
        document.save(update_fields=['verified_at', 'verified_by'])

        serializer = self.get_serializer(document)
        return Response(serializer.data, status=status.HTTP_200_OK)
