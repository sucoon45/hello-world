from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Room, CleaningAssignment, CustomUser # Assuming CustomUser is in users.models

@receiver(post_save, sender=Room)
def auto_create_cleaning_assignment(sender, instance, created, **kwargs):
    """
    Automatically creates a CleaningAssignment when a Room's status
    is set to NEEDS_CLEANING, if no PENDING or IN_PROGRESS assignment already exists.
    """
    if instance.status == Room.RoomStatus.NEEDS_CLEANING:
        # Check if there's already an active (Pending or In Progress) cleaning assignment for this room
        has_active_assignment = CleaningAssignment.objects.filter(
            room=instance,
            status__in=[CleaningAssignment.AssignmentStatus.PENDING, CleaningAssignment.AssignmentStatus.IN_PROGRESS]
        ).exists()

        if not has_active_assignment:
            CleaningAssignment.objects.create(room=instance)
            print(f"Automatically created PENDING cleaning assignment for Room {instance.room_number}")
            # Further logic could be to notify a housekeeping supervisor.

# Consider also what happens if a room status changes FROM NEEDS_CLEANING to something else
# (e.g., AVAILABLE or UNDER_MAINTENANCE) - should existing PENDING assignments be CANCELLED?
# This might be better handled in the place where room status is changed (e.g., RoomViewSet or CleaningAssignmentViewSet).

@receiver(post_save, sender=CleaningAssignment)
def auto_update_room_status_on_cleaning_completion(sender, instance, created, **kwargs):
    """
    Automatically updates the Room status to AVAILABLE when a CleaningAssignment
    is marked as COMPLETED, provided the room was in NEEDS_CLEANING state.
    """
    if instance.status == CleaningAssignment.AssignmentStatus.COMPLETED:
        room = instance.room
        if room.status == Room.RoomStatus.NEEDS_CLEANING:
            room.status = Room.RoomStatus.AVAILABLE
            room.save(update_fields=['status'])
            print(f"Room {room.room_number} status updated to AVAILABLE due to cleaning completion.")
        elif room.status == Room.RoomStatus.OCCUPIED and instance.request_type == "IN_STAY_CLEANING": # Hypothetical in-stay cleaning
            # For in-stay cleaning, room remains OCCUPIED.
            # This requires adding 'request_type' to CleaningAssignment if needed.
            pass
        # If room was UNDER_MAINTENANCE and then cleaned as part of that, it might not become AVAILABLE directly.
        # This logic assumes standard checkout cleaning.

    # If a COMPLETED assignment is reverted (e.g. to PENDING or CANCELLED), should room status change back?
    # This can get complex. For now, only COMPLETED -> AVAILABLE is handled.
