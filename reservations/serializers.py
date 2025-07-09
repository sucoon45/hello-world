from rest_framework import serializers
from .models import Guest, Reservation
from users.serializers import UserSerializer # Potentially for guest user account
from hotel_core.serializers import RoomSerializer # For nested room details

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
            'notes', 'created_at', 'updated_at'
        )
        read_only_fields = ('created_at', 'updated_at', 'total_price')

    def validate(self, data):
        """
        Check that the check_out_date is after the check_in_date.
        Check room availability for the given dates (complex logic, can be a service).
        Check guest capacity.
        """
        # Model's clean method handles some of this, but DRF validation is good too.
        check_in_date = data.get('check_in_date', getattr(self.instance, 'check_in_date', None))
        check_out_date = data.get('check_out_date', getattr(self.instance, 'check_out_date', None))
        room = data.get('room', getattr(self.instance, 'room', None))
        number_of_adults = data.get('number_of_adults', getattr(self.instance, 'number_of_adults', 0))
        number_of_children = data.get('number_of_children', getattr(self.instance, 'number_of_children', 0))


        if check_in_date and check_out_date and check_out_date <= check_in_date:
            raise serializers.ValidationError({"check_out_date": "Check-out date must be after check-in date."})

        if room and (number_of_adults + number_of_children > room.room_type.capacity):
            raise serializers.ValidationError(
                {"guests": f"Number of guests exceeds the capacity of {room.room_type.name} ({room.room_type.capacity})."}
            )

        # Placeholder for room availability check
        # This is a critical and potentially complex piece of logic.
        # It needs to check if the selected room is already booked for any part of the requested period.
        # For now, we'll skip the direct implementation here, assuming it might be handled
        # by a separate service or more detailed model manager method later.
        # On create:
        if room and check_in_date and check_out_date:
            overlapping_reservations = Reservation.objects.filter(
                room=room,
                status__in=[Reservation.ReservationStatus.CONFIRMED, Reservation.ReservationStatus.CHECKED_IN],
                check_in_date__lt=check_out_date, # Existing reservation starts before new one ends
                check_out_date__gt=check_in_date  # Existing reservation ends after new one starts
            )
            if self.instance: # If updating, exclude self from the check
                overlapping_reservations = overlapping_reservations.exclude(pk=self.instance.pk)

            if overlapping_reservations.exists():
                raise serializers.ValidationError(
                    {"room": f"Room {room.room_number} is not available for the selected dates."}
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
