from rest_framework import serializers
from .models import RoomType, Amenity, Room, SeasonalPricing, RoomServiceRequest # Added RoomServiceRequest

class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = '__all__'

class RoomTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomType
        fields = '__all__'

class RoomSerializer(serializers.ModelSerializer):
    # To display amenity names instead of IDs
    amenities = AmenitySerializer(many=True, read_only=True)
    # To display room type name instead of ID
    room_type = serializers.StringRelatedField()
    # For writing, allow passing amenity IDs and room_type ID
    amenity_ids = serializers.PrimaryKeyRelatedField(
        queryset=Amenity.objects.all(), source='amenities', many=True, write_only=True, required=False
    )
    room_type_id = serializers.PrimaryKeyRelatedField(
        queryset=RoomType.objects.all(), source='room_type', write_only=True
    )

    class Meta:
        model = Room
        fields = (
            'id', 'room_number', 'room_type', 'room_type_id', 'status',
            'price_per_night', 'amenities', 'amenity_ids', 'floor'
        )
        read_only_fields = ('room_type', 'amenities',) # These are shown via relationships

    # If you need custom create/update to handle amenity_ids and room_type_id,
    # DRF handles PrimaryKeyRelatedField automatically for 'source' mapping.
    # So, direct assignment in create/update is often not needed unless there's complex logic.
    # def create(self, validated_data):
    #     # amenities_data = validated_data.pop('amenities', None) # Handled by source='amenities' on amenity_ids
    #     # room_type_data = validated_data.pop('room_type') # Handled by source='room_type' on room_type_id
    #     room = Room.objects.create(**validated_data)
    #     # if amenities_data:
    #     #     room.amenities.set(amenities_data)
    #     return room

    # def update(self, instance, validated_data):
    #     # amenities_data = validated_data.pop('amenities', None)
    #     # room_type_data = validated_data.pop('room_type', None)
    #     # instance = super().update(instance, validated_data)
    #     # if amenities_data is not None: # Check for None to allow clearing amenities
    #     #    instance.amenities.set(amenities_data)
    #     # return instance
    # Using source on PrimaryKeyRelatedField should handle this.
    current_effective_price = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = (
            'id', 'room_number', 'room_type', 'room_type_id', 'status',
            'price_per_night', 'current_effective_price', # Added current_effective_price
            'amenities', 'amenity_ids', 'floor'
        )
        read_only_fields = ('room_type', 'amenities', 'current_effective_price')


    def get_current_effective_price(self, obj):
        # obj is the Room instance
        # Calculate price for today. In a real scenario, you might want to pass a date
        # or have a more complex way to determine "current" (e.g., next available booking date).
        from django.utils import timezone # Local import to avoid circularity if this file grows
        today = timezone.now().date()
        return obj.get_price_for_date(today)


class SeasonalPricingSerializer(serializers.ModelSerializer):
    room_type_name = serializers.StringRelatedField(source='room_type.name', read_only=True)

    class Meta:
        model = SeasonalPricing
        fields = (
            'id', 'room_type', 'room_type_name', 'name', 'start_date', 'end_date',
            'price_modifier_type', 'price_modifier_value', 'priority'
        )
        # Ensure room_type is writable via its ID for creation/update
        extra_kwargs = {
            'room_type': {'write_only': True, 'required': True}
        }
        # read_only_fields = ('room_type_name',) # Already handled by source and StringRelatedField

    def validate(self, data):
        # Model's clean() method already has some validation.
        # Additional cross-field validation can go here if needed.
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "End date cannot be before start date."})

        # Check for overlapping rules for the same room_type and same priority
        # This can be complex. A simpler approach is to rely on admin diligence or a unique_together constraint
        # on (room_type, start_date, priority) and (room_type, end_date, priority) if exact overlaps are disallowed.
        # For now, we will rely on model's ordering and admin's responsibility.
        # A more advanced validation could check if the date range for a given room_type and priority
        # overlaps with an existing rule.

        return data


class RoomServiceRequestSerializer(serializers.ModelSerializer):
    room_number = serializers.StringRelatedField(source='room.room_number', read_only=True)
    reservation_id_display = serializers.PrimaryKeyRelatedField(source='reservation', read_only=True) # Just to show ID
    requested_by_username = serializers.StringRelatedField(source='requested_by.username', read_only=True)
    assigned_to_username = serializers.StringRelatedField(source='assigned_to.username', read_only=True)

    # Writable fields for creation by guest/staff
    room_id = serializers.PrimaryKeyRelatedField(
        queryset=Room.objects.all(), source='room', write_only=True
    )
    # Reservation can be optional. If provided, it should be an ID.
    reservation_id = serializers.PrimaryKeyRelatedField(
        queryset='reservations.Reservation'.objects.all(), # Use string to avoid circular import if Reservation model is in another app
        source='reservation',
        write_only=True,
        required=False, # Making it optional
        allow_null=True
    )
    # requested_by will be set automatically based on the logged-in user in the view.

    class Meta:
        model = RoomServiceRequest
        fields = (
            'id', 'reservation', 'reservation_id_display', 'reservation_id',
            'room', 'room_number', 'room_id',
            'request_type', 'description', 'status',
            'requested_by', 'requested_by_username', 'requested_at',
            'assigned_to', 'assigned_to_username', 'completed_at',
            'notes', 'price'
        )
        read_only_fields = (
            'reservation', # Displayed via reservation_id_display
            'room',        # Displayed via room_number
            'requested_by',
            'requested_at',
            'completed_at',
            # Potentially 'assigned_to', 'status', 'price', 'notes' are only updatable by staff
            # For now, let's assume staff can update them via PATCH.
            # Guest might only create with description, request_type.
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically import Reservation model for the queryset to avoid circular dependency at module load time
        if 'reservations.Reservation' == 'reservations.Reservation': # Placeholder for actual check or better way
            from reservations.models import Reservation as ReservationModel
            if 'reservation_id' in self.fields:
                 self.fields['reservation_id'].queryset = ReservationModel.objects.all()

        # Make fields writable/read-only based on user role and action (more advanced)
        # For example, if request.user is a guest, some fields become read_only.
        # request = self.context.get('request', None)
        # if request and request.user and not request.user.is_staff: # Example: Guest user
        #     make_staff_fields_readonly = ['status', 'assigned_to', 'notes', 'price', 'completed_at']
        #     for field_name in make_staff_fields_readonly:
        #         if field_name in self.fields:
        #             self.fields[field_name].read_only = True
