from django.db import models
from django.conf import settings # To link to CustomUser
from hotel_core.models import Room
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone

class Guest(models.Model):
    # If a guest can create an account, link to the CustomUser model
    user_account = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, # Keep guest record even if user account is deleted
        null=True, blank=True,
        related_name='guest_profile'
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True) # Make email unique for guests as well
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    # Add other fields like 'date_of_birth', 'nationality', 'id_document_type', 'id_document_number'

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

class Reservation(models.Model):
    class ReservationStatus(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        CONFIRMED = "CONFIRMED", _("Confirmed")
        CHECKED_IN = "CHECKED_IN", _("Checked-In")
        CHECKED_OUT = "CHECKED_OUT", _("Checked-Out")
        CANCELLED = "CANCELLED", _("Cancelled")
        NO_SHOW = "NO_SHOW", _("No Show")

    guest = models.ForeignKey(Guest, on_delete=models.PROTECT, related_name="reservations") # Protect guest if they have reservations
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="reservations") # Protect room if it has reservations
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    number_of_adults = models.PositiveIntegerField(default=1)
    number_of_children = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=ReservationStatus.choices,
        default=ReservationStatus.PENDING,
    )
    total_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True) # Can be calculated
    notes = models.TextField(blank=True, null=True) # Special requests, etc.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # Ensure check_out_date is after check_in_date
        if self.check_in_date and self.check_out_date and self.check_out_date <= self.check_in_date:
            raise ValidationError(_("Check-out date must be after check-in date."))

        # Ensure check_in_date is not in the past for new reservations
        if not self.pk and self.check_in_date and self.check_in_date < timezone.now().date():
             raise ValidationError(_("Check-in date cannot be in the past for new reservations."))

        # Potentially add validation for room capacity vs number of guests
        if self.room and (self.number_of_adults + self.number_of_children > self.room.room_type.capacity):
            raise ValidationError(_(f"Number of guests exceeds the capacity of {self.room.room_type.name} ({self.room.room_type.capacity})."))

    def calculate_total_price(self):
        if self.check_in_date and self.check_out_date and self.room:
            duration = (self.check_out_date - self.check_in_date).days
            if duration <= 0: # Should be caught by clean method, but good to be safe
                return 0
            return duration * self.room.price_per_night
        return None

    def save(self, *args, **kwargs):
        if not self.total_price: # Calculate price if not set
            self.total_price = self.calculate_total_price()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Reservation for {self.guest} in {self.room.room_number} from {self.check_in_date} to {self.check_out_date}"
