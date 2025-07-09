from django.core.mail import send_mail
from django.conf import settings
from .email_templates import (
    CONFIRMATION_EMAIL_SUBJECT, CONFIRMATION_EMAIL_BODY_TEXT,
    REMINDER_EMAIL_SUBJECT, REMINDER_EMAIL_BODY_TEXT,
    CANCELLATION_EMAIL_SUBJECT, CANCELLATION_EMAIL_BODY_TEXT,
)

def send_reservation_confirmation_email(reservation):
    """
    Sends a confirmation email to the guest.
    """
    if not reservation.guest.email:
        # Log this or handle as needed - cannot send email without an address
        print(f"Error: Guest {reservation.guest.id} has no email address for reservation {reservation.id}.")
        return

    subject = CONFIRMATION_EMAIL_SUBJECT
    message = CONFIRMATION_EMAIL_BODY_TEXT.format(
        guest_name=reservation.guest.first_name,
        reservation_id=reservation.id,
        room_number=reservation.room.room_number,
        room_type=reservation.room.room_type.name,
        check_in_date=reservation.check_in_date.strftime('%Y-%m-%d'),
        check_out_date=reservation.check_out_date.strftime('%Y-%m-%d'),
        num_adults=reservation.number_of_adults,
        num_children=reservation.number_of_children,
        total_price=f"{reservation.total_price:.2f}",
        group_name=reservation.group_name if reservation.group_name else "N/A"
    )
    from_email = settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@hotel.com'
    recipient_list = [reservation.guest.email]

    try:
        send_mail(subject, message, from_email, recipient_list, fail_silently=False)
        print(f"Confirmation email sent to {reservation.guest.email} for reservation {reservation.id}")
    except Exception as e:
        # Log the exception
        print(f"Error sending confirmation email for reservation {reservation.id}: {e}")


def send_reservation_reminder_email(reservation):
    """
    Sends a reminder email to the guest (e.g., a day before check-in).
    This function would typically be called by a scheduled task.
    """
    if not reservation.guest.email:
        print(f"Error: Guest {reservation.guest.id} has no email address for reservation {reservation.id} reminder.")
        return

    subject = REMINDER_EMAIL_SUBJECT
    message = REMINDER_EMAIL_BODY_TEXT.format(
        guest_name=reservation.guest.first_name,
        reservation_id=reservation.id,
        room_number=reservation.room.room_number,
        room_type=reservation.room.room_type.name,
        check_in_date=reservation.check_in_date.strftime('%Y-%m-%d'),
        check_out_date=reservation.check_out_date.strftime('%Y-%m-%d'),
    )
    from_email = settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@hotel.com'
    recipient_list = [reservation.guest.email]

    try:
        send_mail(subject, message, from_email, recipient_list, fail_silently=False)
        print(f"Reminder email sent to {reservation.guest.email} for reservation {reservation.id}")
    except Exception as e:
        print(f"Error sending reminder email for reservation {reservation.id}: {e}")


def send_reservation_cancellation_email(reservation):
    """
    Sends a cancellation confirmation email to the guest.
    """
    if not reservation.guest.email:
        print(f"Error: Guest {reservation.guest.id} has no email address for reservation {reservation.id} cancellation.")
        return

    subject = CANCELLATION_EMAIL_SUBJECT
    message = CANCELLATION_EMAIL_BODY_TEXT.format(
        guest_name=reservation.guest.first_name,
        reservation_id=reservation.id,
        room_number=reservation.room.room_number,
        room_type=reservation.room.room_type.name,
        check_in_date=reservation.check_in_date.strftime('%Y-%m-%d'),
        check_out_date=reservation.check_out_date.strftime('%Y-%m-%d'),
    )
    from_email = settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@hotel.com'
    recipient_list = [reservation.guest.email]

    try:
        send_mail(subject, message, from_email, recipient_list, fail_silently=False)
        print(f"Cancellation email sent to {reservation.guest.email} for reservation {reservation.id}")
    except Exception as e:
        print(f"Error sending cancellation email for reservation {reservation.id}: {e}")
