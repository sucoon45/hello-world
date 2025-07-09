from decimal import Decimal
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
        limit_choices_to={'role__in': ['ADMIN', 'FRONT_DESK', 'HOUSEKEEPING']}, # Example: Limit to staff roles
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
