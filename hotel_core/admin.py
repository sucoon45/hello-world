from django.contrib import admin
from .models import RoomType, Amenity, Room

@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'capacity', 'description')
    search_fields = ('name',)

@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'room_type', 'status', 'price_per_night', 'floor')
    list_filter = ('status', 'room_type', 'floor')
    search_fields = ('room_number',)
    autocomplete_fields = ('room_type',) # If you have many room types
    filter_horizontal = ('amenities',) # For easier selection of many-to-many fields
