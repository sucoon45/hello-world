from rest_framework import serializers
from .models import RoomType, Amenity, Room

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
