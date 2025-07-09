from django.db import models
from django.conf import settings # To link to CustomUser
from hotel_core.models import Room
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
import uuid


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

    # Fields for Group Reservations
    group_name = models.CharField(max_length=255, blank=True, null=True, help_text="Name for the group booking, if applicable.")
    group_identifier = models.UUIDField(null=True, blank=True, editable=False, help_text="Unique identifier for a group of reservations.")

    # Fields for Early Check-in / Late Check-out
    requested_early_check_in = models.DateTimeField(null=True, blank=True, help_text="Requested early check-in date and time.")
    is_early_check_in_approved = models.BooleanField(default=False, help_text="Is early check-in approved by staff.")
    early_check_in_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Fee for approved early check-in.")

    requested_late_check_out = models.DateTimeField(null=True, blank=True, help_text="Requested late check-out date and time.")
    is_late_check_out_approved = models.BooleanField(default=False, help_text="Is late check-out approved by staff.")
    late_check_out_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Fee for approved late check-out.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # If part of a group and no identifier, generate one (only for the first reservation of the group)
        # This logic might be better handled at the ViewSet/service layer when creating group bookings
        # to ensure all reservations in a single group creation get the same ID.
        # For now, if group_name is given and no group_identifier, we might assume it's a new group.
        # However, this simple model-level save won't coordinate across multiple new reservations for a group.
        # if self.group_name and not self.group_identifier:
        #    self.group_identifier = uuid.uuid4() # This would make every reservation its own group if not careful

        # Recalculate total_price to include base price + any approved fees
        base_price = self.calculate_total_price() # Price based on room and duration

        approved_early_fee = 0
        if self.is_early_check_in_approved and self.early_check_in_fee:
            approved_early_fee = self.early_check_in_fee

        approved_late_fee = 0
        if self.is_late_check_out_approved and self.late_check_out_fee:
            approved_late_fee = self.late_check_out_fee

        self.total_price = (base_price if base_price is not None else 0) + approved_early_fee + approved_late_fee

        super().save(*args, **kwargs)

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
    def __str__(self):
        return f"Reservation for {self.guest} in {self.room.room_number} from {self.check_in_date} to {self.check_out_date}"


# Model for Storing Guest ID Proofs/Documents
def guest_document_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/guest_docs/guest_<id>/<filename>
    return f'guest_docs/guest_{instance.guest.id}/{filename}'

class GuestDocument(models.Model):
    class DocumentType(models.TextChoices):
        PASSPORT = 'PASSPORT', _('Passport')
        ID_CARD = 'ID_CARD', _('ID Card')
        DRIVERS_LICENSE = 'DRIVERS_LICENSE', _("Driver's License")
        OTHER = 'OTHER', _('Other')

    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
        default=DocumentType.OTHER,
    )
    document_number = models.CharField(max_length=100, blank=True, help_text="Number of the identification document.")
    document_image = models.ImageField(upload_to=guest_document_path, help_text="Scanned image of the document.")

    uploaded_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='verified_documents',
        help_text="Staff who verified this document."
    )

    def __str__(self):
        return f"{self.get_document_type_display()} for {self.guest} ({self.document_number or 'N/A'})"
