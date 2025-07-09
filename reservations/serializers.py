from django.utils import timezone
from rest_framework import serializers
from .models import Guest, Reservation
from users.serializers import UserSerializer # Potentially for guest user account
from hotel_core.serializers import RoomSerializer # For nested room details
from hotel_core.models import Room


class GuestSerializer(serializers.ModelSerializer):
    # user_account = UserSerializer(read_only=True) # Example if you want to nest user details
    user_account_id = serializers.IntegerField(source='user_account.id', read_only=True) # Or just the ID

    class Meta:
        model = Guest
        fields = (
            'id', 'first_name', 'last_name', 'email', 'phone_number',
            'address', 'user_account_id' # 'user_account'
        )
        # If guest creation can link to an existing user or create one,
        # you might need a writable UserSerializer field or custom create logic.

class ReservationSerializer(serializers.ModelSerializer):
    guest = GuestSerializer(read_only=True) # Display guest details
    guest_id = serializers.PrimaryKeyRelatedField(
        queryset=Guest.objects.all(), source='guest', write_only=True
    )

    room = RoomSerializer(read_only=True) # Display full room details
    room_id = serializers.PrimaryKeyRelatedField(
        queryset=Room.objects.all(), source='room', write_only=True
    )

    # Make total_price read-only as it's calculated by the model
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)


    class Meta:
        model = Reservation
        fields = (
            'id', 'guest', 'guest_id', 'room', 'room_id', 'check_in_date', 'check_out_date',
            'number_of_adults', 'number_of_children', 'status', 'total_price',
            'notes',
            'group_name', 'group_identifier',
            # Early check-in / Late check-out fields
            'requested_early_check_in', 'is_early_check_in_approved', 'early_check_in_fee',
            'requested_late_check_out', 'is_late_check_out_approved', 'late_check_out_fee',
            'created_at', 'updated_at'
        )
        read_only_fields = (
            'created_at', 'updated_at', 'total_price', 'group_identifier',
            'is_early_check_in_approved', 'early_check_in_fee', # Typically set by staff
            'is_late_check_out_approved', 'late_check_out_fee',   # Typically set by staff
        )

    def validate_requested_early_check_in(self, value):
        # Value is a datetime object
        # Check if requested_early_check_in is before the standard check_in_date (time part matters)
        # This requires knowing the standard check-in time for the hotel.
        # For now, we'll just ensure it's on the same day as check_in_date or earlier.
        # A more robust validation would compare it against hotel's standard check-in time on check_in_date.
        check_in_date = self.initial_data.get('check_in_date') # Get from original request data
        if check_in_date and value:
            if not isinstance(check_in_date, datetime.date):
                 check_in_date = datetime.datetime.strptime(check_in_date, '%Y-%m-%d').date()

            # Standard check-in time (e.g. 3 PM). This should be a hotel setting.
            standard_check_in_datetime = timezone.make_aware(datetime.datetime.combine(check_in_date, datetime.time(15, 0))) # Example: 3 PM

            if value >= standard_check_in_datetime:
                raise serializers.ValidationError("Requested early check-in time must be before the standard check-in time.")
            if value.date() > check_in_date :
                 raise serializers.ValidationError("Early check-in cannot be requested for a date after the reservation check-in date.")
        return value

    def validate_requested_late_check_out(self, value):
        # Value is a datetime object
        # Check if requested_late_check_out is after the standard check_out_date (time part matters)
        check_out_date = self.initial_data.get('check_out_date')
        if check_out_date and value:
            if not isinstance(check_out_date, datetime.date):
                check_out_date = datetime.datetime.strptime(check_out_date, '%Y-%m-%d').date()

            # Standard check-out time (e.g. 11 AM). This should be a hotel setting.
            standard_check_out_datetime = timezone.make_aware(datetime.datetime.combine(check_out_date, datetime.time(11, 0))) # Example: 11 AM

            if value <= standard_check_out_datetime:
                raise serializers.ValidationError("Requested late check-out time must be after the standard check-out time.")
            if value.date() < check_out_date:
                raise serializers.ValidationError("Late check-out cannot be requested for a date before the reservation check-out date.")
        return value

    def validate(self, data):
        """
        Check that the check_out_date is after the check_in_date.
        Check room availability for the given dates.
        Check guest capacity against room capacity.
        Ensure room is in a bookable state.
        """
        # Get data, falling back to instance data if not provided (for updates)
        check_in_date = data.get('check_in_date', getattr(self.instance, 'check_in_date', None))
        check_out_date = data.get('check_out_date', getattr(self.instance, 'check_out_date', None))

        # The 'room' key in `data` will hold the Room instance due to `source='room'` on `room_id`
        # if room_id is passed in the request. If the full room object is passed, it's used directly.
        room_instance = data.get('room', getattr(self.instance, 'room', None))

        # number_of_adults and number_of_children default to instance values if not provided,
        # or 1 and 0 respectively for new instances if not specified in request.
        default_adults = 1
        default_children = 0
        if self.instance:
            default_adults = self.instance.number_of_adults
            default_children = self.instance.number_of_children

        number_of_adults = data.get('number_of_adults', default_adults)
        number_of_children = data.get('number_of_children', default_children)

        # --- Basic Date Validations ---
        if not (check_in_date and check_out_date):
             raise serializers.ValidationError({"dates": "Both check-in and check-out dates are required."})

        if check_out_date <= check_in_date:
            raise serializers.ValidationError({"check_out_date": "Check-out date must be after check-in date."})

        # For new reservations, check_in_date cannot be in the past.
        if not self.instance and check_in_date < timezone.now().date(): # `self.instance` is None for create operations
            raise serializers.ValidationError({"check_in_date": "Check-in date cannot be in the past for new reservations."})

        # --- Room and Guest Count Validations ---
        if not room_instance:
            # This case implies 'room_id' was not provided or was invalid if 'room' is not in data.
            # If 'room' (resolved from room_id) is None, it means PrimaryKeyRelatedField found no such room.
            # The field itself (room_id) would have raised a "does_not_exist" or "invalid_pk" error before this global validate.
            # So, this specific check might be redundant if room_id is required=True.
            # However, if room_id is not required or allow_null=True, this check is useful.
            # For now, room_id is write_only=True (implicitly required=True).
            pass # Field-level validation on room_id should catch missing/invalid room.

        if room_instance:
            if (number_of_adults + number_of_children) == 0:
                raise serializers.ValidationError({"guests": "At least one guest (adult or child) is required."})
            if (number_of_adults + number_of_children) > room_instance.room_type.capacity:
                raise serializers.ValidationError(
                    {"guests": f"Number of guests ({number_of_adults + number_of_children}) "
                               f"exceeds the capacity of room type '{room_instance.room_type.name}' ({room_instance.room_type.capacity})."}
                )

            # --- Room Availability Check ---
            # 1. Check Room's own operational status (e.g., UNDER_MAINTENANCE)
            # These statuses make a room non-bookable regardless of date.
            non_bookable_room_statuses = [
                Room.RoomStatus.UNDER_MAINTENANCE,
                # Add Room.RoomStatus.DECOMMISSIONED if such a status exists
            ]
            if room_instance.status in non_bookable_room_statuses:
                raise serializers.ValidationError(
                    {"room": f"Room {room_instance.room_number} is currently {room_instance.get_status_display()} and cannot be booked."}
                )

            # A room that NEEDS_CLEANING might be bookable if it can be cleaned before check-in.
            # This logic can be complex (e.g. depends on housekeeping schedule).
            # For now, we'll allow booking a room that NEEDS_CLEANING, assuming it will be cleaned.
            # If it should NOT be bookable, add Room.RoomStatus.NEEDS_CLEANING to non_bookable_room_statuses.

            # 2. Check for conflicting reservations (double booking)
            conflicting_reservation_statuses = [
                Reservation.ReservationStatus.CONFIRMED,
                Reservation.ReservationStatus.CHECKED_IN,
            ]

            # Query for reservations that overlap with the requested period for the given room.
            # Overlap condition: Existing reservation's start_date < Requested end_date
            # AND Existing reservation's end_date > Requested start_date
            query = Reservation.objects.filter(
                room=room_instance,
                status__in=conflicting_reservation_statuses,
                check_in_date__lt=check_out_date, # Existing res starts before new one ends
                check_out_date__gt=check_in_date  # Existing res ends after new one starts
            )

            if self.instance: # If updating an existing reservation, exclude it from the conflict check
                query = query.exclude(pk=self.instance.pk)

            if query.exists():
                # You could provide more details about the conflict if desired
                # conflicting_booking = query.first()
                raise serializers.ValidationError(
                    {"room": f"Room {room_instance.room_number} is not available for the selected dates due to an existing booking."}
                )

        return data

    # The save method in the serializer can call model's calculate_total_price
    # or the model's save method can handle it as it does now.
    # def create(self, validated_data):
    #     reservation = Reservation(**validated_data)
    #     reservation.total_price = reservation.calculate_total_price() # Ensure it's calculated
    #     reservation.save() # Model's save will also try to calculate if not present
    #     return reservation

    # def update(self, instance, validated_data):
    #     instance = super().update(instance, validated_data)
    #     instance.total_price = instance.calculate_total_price() # Recalculate if dates/room changed
    #     instance.save()
    #     return instance
    # The model's save() method already handles total_price calculation, so this might be redundant.
    # However, explicit calculation in serializer's save can be useful if you want to return the calculated
    # price immediately in the response of a POST/PUT without an additional DB query.
    # For now, relying on model's save() is fine.


class GuestDocumentSerializer(serializers.ModelSerializer):
    # Make guest field read-only on update, but writable on create by guest_id
    # guest = GuestSerializer(read_only=True) # Or StringRelatedField
    guest_id = serializers.PrimaryKeyRelatedField(
        queryset=Guest.objects.all(), source='guest', write_only=True
    )
    # document_image is used for upload (write) by DRF due to ModelSerializer mapping
    # document_image_url is for explicit read-only URL representation
    document_image_url = serializers.SerializerMethodField()
    verified_by_username = serializers.StringRelatedField(source='verified_by.username', read_only=True)


    class Meta:
        model = GuestDocument
        fields = (
            'id', 'guest', 'guest_id', 'document_type', 'document_number',
            'document_image', 'document_image_url',
            'uploaded_at', 'verified_at', 'verified_by', 'verified_by_username'
        )
        # 'guest' is implicitly read_only if guest_id is the write source.
        # We mark document_image as write_only if document_image_url is the preferred read source for the image path.
        # However, DRF usually handles ImageField to return its URL path on read by default.
        # Let's keep document_image as is, DRF should return its path on GET.
        # If we want an absolute URL, SerializerMethodField is better.
        read_only_fields = ('guest', 'uploaded_at', 'verified_at', 'verified_by', 'verified_by_username', 'document_image_url')
        extra_kwargs = {
            'document_image': {'write_only': True} # Make the actual image field write-only if url is provided for read
        }


    def get_document_image_url(self, obj):
        request = self.context.get('request')
        if obj.document_image and request:
            return request.build_absolute_uri(obj.document_image.url)
        elif obj.document_image: # Fallback if no request context (e.g. in shell)
            return obj.document_image.url
        return None

    def validate_document_image(self, value):
        # Example validation: max size 2MB
        if value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("Image size should not exceed 2MB.")
        # Can add content type validation too
        return value
