CONFIRMATION_EMAIL_SUBJECT = "Your Reservation is Confirmed!"

CONFIRMATION_EMAIL_BODY_TEXT = """
Dear {guest_name},

Thank you for your reservation at Our Hotel!

Your booking details are as follows:
Reservation ID: {reservation_id}
Room: {room_number} ({room_type})
Check-in Date: {check_in_date}
Check-out Date: {check_out_date}
Number of Adults: {num_adults}
Number of Children: {num_children}
Total Price: ${total_price}

Group Name: {group_name}

We look forward to welcoming you!

Sincerely,
The Hotel Management Team
"""

REMINDER_EMAIL_SUBJECT = "Upcoming Reservation Reminder"

REMINDER_EMAIL_BODY_TEXT = """
Dear {guest_name},

This is a friendly reminder about your upcoming reservation at Our Hotel.

Your booking details:
Reservation ID: {reservation_id}
Room: {room_number} ({room_type})
Check-in Date: {check_in_date}
Check-out Date: {check_out_date}

Please ensure you have your booking confirmation and ID ready for check-in.

We look forward to your visit!

Sincerely,
The Hotel Management Team
"""

CANCELLATION_EMAIL_SUBJECT = "Your Reservation has been Cancelled"

CANCELLATION_EMAIL_BODY_TEXT = """
Dear {guest_name},

This email confirms that your reservation (ID: {reservation_id}) at Our Hotel has been successfully cancelled.

Details of the cancelled reservation:
Room: {room_number} ({room_type})
Check-in Date: {check_in_date}
Check-out Date: {check_out_date}

If you did not request this cancellation, please contact us immediately.

We hope to welcome you some other time.

Sincerely,
The Hotel Management Team
"""
