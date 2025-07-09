from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _
from users.models import CustomUser # For limit_choices_to

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
        BOOKED = "BOOKED", _("Booked") # New status
        OCCUPIED = "OCCUPIED", _("Occupied")
        NEEDS_CLEANING = "NEEDS_CLEANING", _("Needs Cleaning")
        UNDER_MAINTENANCE = "UNDER_MAINTENANCE", _("Under Maintenance")
        # Add other statuses as needed, e.g., DECOMMISSIONED

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

    def get_price_for_date(self, target_date):
        """
        Calculates the effective price for this room on a specific target_date,
        considering seasonal pricing rules.
        """
        base_price = self.price_per_night

        # Find active seasonal pricing rules for this room's type on the target_date
        # Rules are ordered by priority (desc) then start_date
        active_rules = SeasonalPricing.objects.filter(
            room_type=self.room_type,
            start_date__lte=target_date,
            end_date__gte=target_date
        ).order_by('-priority', 'start_date') # Ensure consistent high-priority application

        # Apply the highest priority rule found (if any)
        # More complex logic could involve combining rules, but highest priority override/adjustment is common.
        if active_rules.exists():
            applicable_rule = active_rules.first() # Highest priority rule for the date

            if applicable_rule.price_modifier_type == SeasonalPricing.ModifierType.FIXED_OVERRIDE:
                return applicable_rule.price_modifier_value # This is the absolute new price

            elif applicable_rule.price_modifier_type == SeasonalPricing.ModifierType.PERCENTAGE:
                adjustment_factor = applicable_rule.price_modifier_value / Decimal('100')
                return base_price * (Decimal('1') + adjustment_factor)

            # Add other modifier types here if implemented (e.g., FIXED_ADJUSTMENT)
            # elif applicable_rule.price_modifier_type == SeasonalPricing.ModifierType.FIXED_ADJUSTMENT:
            # return base_price + applicable_rule.price_modifier_value

        return base_price # No active seasonal rule, return room's base price


class SeasonalPricing(models.Model):
    class ModifierType(models.TextChoices):
        PERCENTAGE = 'PERCENTAGE', _('Percentage Adjustment') # e.g., 10 for +10%, -5 for -5%
        FIXED_OVERRIDE = 'FIXED_OVERRIDE', _('Fixed Price Override') # Absolute new price
        # FIXED_ADJUSTMENT = 'FIXED_ADJUSTMENT', _('Fixed Amount Adjustment') # e.g., +20 or -10 from base

    room_type = models.ForeignKey(RoomType, on_delete=models.CASCADE, related_name='seasonal_pricings')
    name = models.CharField(max_length=255, help_text="e.g., 'Summer High Season', 'Weekend Special'")
    start_date = models.DateField()
    end_date = models.DateField()

    price_modifier_type = models.CharField(
        max_length=20,
        choices=ModifierType.choices,
        default=ModifierType.FIXED_OVERRIDE,
    )
    # For PERCENTAGE, stores percentage (e.g., 10.00 for 10%, -5.00 for -5%).
    # For FIXED_OVERRIDE, stores the absolute new price.
    price_modifier_value = models.DecimalField(max_digits=10, decimal_places=2)

    # To handle precedence if multiple rules apply to the same date for the same room_type
    priority = models.IntegerField(default=0, help_text="Higher numbers have higher precedence.")

    # Optional: Applicable days of the week (e.g., "0,1,6" for Mon, Tue, Sun (Python's weekday()) or specific model)
    # For simplicity, this example assumes the rule applies to all days within its start_date and end_date.
    # days_of_week = models.CharField(max_length=15, blank=True, null=True, help_text="Comma-separated days (0=Mon, 6=Sun). Empty for all.")


    class Meta:
        verbose_name = "Seasonal Pricing Rule"
        verbose_name_plural = "Seasonal Pricing Rules"
        ordering = ['-priority', 'start_date'] # Higher priority first

    def __str__(self):
        return f"{self.name} for {self.room_type.name} ({self.start_date} to {self.end_date})"

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise models.ValidationError(_("End date cannot be before start date."))

        if self.price_modifier_type == self.ModifierType.PERCENTAGE:
            if self.price_modifier_value > 1000 or self.price_modifier_value < -99.99 : # Arbitrary sanity check for percentage
                 raise models.ValidationError(_("Percentage adjustment seems too extreme. Enter value like 10 for 10% or -5 for -5%."))
        elif self.price_modifier_type == self.ModifierType.FIXED_OVERRIDE:
            if self.price_modifier_value < 0:
                raise models.ValidationError(_("Fixed override price cannot be negative."))


class RoomServiceRequest(models.Model):
    class RequestType(models.TextChoices):
        FOOD_BEVERAGE = 'FOOD_BEVERAGE', _('Food & Beverage')
        TOILETRIES = 'TOILETRIES', _('Toiletries')
        MAINTENANCE_ISSUE = 'MAINTENANCE_ISSUE', _('Maintenance Issue')
        OTHER = 'OTHER', _('Other')

    class RequestStatus(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
        COMPLETED = 'COMPLETED', _('Completed')
        CANCELLED = 'CANCELLED', _('Cancelled')

    # Nullable if request can be made for a room not tied to an active reservation (e.g. by staff for general room prep)
    # Or non-nullable if always tied to a guest's stay. Let's make it nullable for flexibility.
    reservation = models.ForeignKey(
        'reservations.Reservation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='service_requests'
    )
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='service_requests')

    request_type = models.CharField(max_length=20, choices=RequestType.choices, default=RequestType.OTHER)
    description = models.TextField(help_text="Details of the request, e.g., '2x Club Sandwich, 1x Coke', or 'Leaking Faucet'")
    status = models.CharField(max_length=20, choices=RequestStatus.choices, default=RequestStatus.PENDING)

    # Assuming CustomUser model is at 'users.CustomUser'
    requested_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL, # Keep request even if user is deleted
        null=True, blank=True, # Can be anonymous or system-generated if needed
        related_name='made_service_requests',
        help_text="User who made the request (guest or staff)"
    )
    requested_at = models.DateTimeField(auto_now_add=True)

    assigned_to = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_service_tasks',
        limit_choices_to={'role__in': [
            CustomUser.Role.ADMIN,
            CustomUser.Role.FRONT_DESK,
            CustomUser.Role.HOUSEKEEPING,
            CustomUser.Role.MAINTENANCE  # Add MAINTENANCE role
        ]},
        help_text="Staff member assigned to this task"
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True, help_text="Internal notes by staff regarding the request.")
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Price if the service/item is billable. Added to guest's folio.")

    class Meta:
        verbose_name = "Room Service Request"
        verbose_name_plural = "Room Service Requests"
        ordering = ['-requested_at']

    def __str__(self):
        return f"{self.get_request_type_display()} for Room {self.room.room_number} (Status: {self.get_status_display()})"

    def save(self, *args, **kwargs):
        if self.status == self.RequestStatus.COMPLETED and not self.completed_at:
            from django.utils import timezone # Local import
            self.completed_at = timezone.now()
        # If status changes from COMPLETED to something else, clear completed_at? (optional)
        # elif self.status != self.RequestStatus.COMPLETED and self.completed_at:
        #     self.completed_at = None
        super().save(*args, **kwargs)


class CleaningAssignment(models.Model):
    class AssignmentStatus(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
        COMPLETED = 'COMPLETED', _('Completed')
        CANCELLED = 'CANCELLED', _('Cancelled') # e.g. room re-occupied, or issue resolved otherwise

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='cleaning_assignments')
    assigned_to = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cleaning_tasks',
        limit_choices_to={'role': CustomUser.Role.HOUSEKEEPING} # Only assign to Housekeeping staff
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=AssignmentStatus.choices,
        default=AssignmentStatus.PENDING
    )
    notes = models.TextField(blank=True, null=True, help_text="Notes from supervisor or staff.")
    cleaned_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when cleaning was completed.")

    class Meta:
        verbose_name = "Cleaning Assignment"
        verbose_name_plural = "Cleaning Assignments"
        ordering = ['-assigned_at']

    def __str__(self):
        assignee_name = self.assigned_to.username if self.assigned_to else "Unassigned"
        return f"Cleaning for Room {self.room.room_number} - {self.get_status_display()} (Assigned to: {assignee_name})"

    def save(self, *args, **kwargs):
        # If status is COMPLETED and cleaned_at is not set, set it now.
        if self.status == self.AssignmentStatus.COMPLETED and not self.cleaned_at:
            from django.utils import timezone # Local import
            self.cleaned_at = timezone.now()

        # If status is changed from COMPLETED to something else, clear cleaned_at (optional behavior)
        # elif self.status != self.AssignmentStatus.COMPLETED and self.cleaned_at:
        #     self.cleaned_at = None
        super().save(*args, **kwargs)


# --- Laundry and Linen Management Models (Basic Structure) ---

class LinenType(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="e.g., 'Bath Towel', 'Hand Towel', 'King Sheet Set', 'Pillowcase'")
    description = models.TextField(blank=True, null=True)
    # Potentially add fields like 'standard_lifespan_days' or 'cost_per_item' for advanced inventory.

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Linen Type"
        verbose_name_plural = "Linen Types"
        ordering = ['name']


class RoomLinenInventory(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='linen_inventory')
    linen_type = models.ForeignKey(LinenType, on_delete=models.PROTECT, related_name='room_stocks') # Protect LinenType from deletion if in use

    quantity_par = models.PositiveIntegerField(default=0, help_text="Standard stock quantity (par level) for this linen type in this room.")
    current_quantity_clean = models.PositiveIntegerField(default=0, help_text="Current count of clean items of this linen type in the room.")
    # last_changed_date could track when linen was last fully replaced or par level was met.
    last_restocked_date = models.DateField(null=True, blank=True, help_text="Date when this linen item was last restocked to par in the room.")
    # last_sent_to_laundry_date = models.DateField(null=True, blank=True) # More complex tracking

    class Meta:
        verbose_name = "Room Linen Inventory"
        verbose_name_plural = "Room Linen Inventories"
        unique_together = ('room', 'linen_type') # Each linen type should have one entry per room
        ordering = ['room__room_number', 'linen_type__name']

    def __str__(self):
        return f"{self.linen_type.name} in Room {self.room.room_number} (Clean: {self.current_quantity_clean}/{self.quantity_par})"

    def needs_restock(self):
        return self.current_quantity_clean < self.quantity_par

    # Future methods could include:
    # - mark_as_sent_to_laundry(quantity)
    # - mark_as_returned_from_laundry(quantity)
    # - restock_to_par()
