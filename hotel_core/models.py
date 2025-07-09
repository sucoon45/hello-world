from django.db import models
from django.utils.translation import gettext_lazy as _

class Amenity(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class RoomType(models.Model):
    name = models.CharField(max_length=100, unique=True)  # e.g., Single, Double, Suite
    description = models.TextField(blank=True, null=True)
    capacity = models.PositiveIntegerField(default=1) # Number of guests it can accommodate

    def __str__(self):
        return self.name

class Room(models.Model):
    class RoomStatus(models.TextChoices):
        AVAILABLE = "AVAILABLE", _("Available")
        OCCUPIED = "OCCUPIED", _("Occupied")
        UNDER_MAINTENANCE = "UNDER_MAINTENANCE", _("Under Maintenance")
        NEEDS_CLEANING = "NEEDS_CLEANING", _("Needs Cleaning")
        # Add other statuses as needed

    room_number = models.CharField(max_length=10, unique=True)
    room_type = models.ForeignKey(RoomType, on_delete=models.CASCADE, related_name="rooms")
    status = models.CharField(
        max_length=20,
        choices=RoomStatus.choices,
        default=RoomStatus.AVAILABLE,
    )
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    amenities = models.ManyToManyField(Amenity, blank=True, related_name="rooms")
    floor = models.IntegerField(blank=True, null=True)
    # Add other fields like 'is_smoking_allowed', 'view_type', etc.

    def __str__(self):
        return f"Room {self.room_number} ({self.room_type.name})"
