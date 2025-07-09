from django.utils import timezone
from django.db import transaction
from decimal import Decimal

from .models import Invoice, InvoiceLineItem
from reservations.models import Reservation # Assuming Reservation is in reservations.models
from hotel_core.models import RoomServiceRequest # Assuming RoomServiceRequest is in hotel_core.models

def generate_invoice_for_reservation(reservation: Reservation, issue_date=None, due_date_days=15):
    """
    Generates an Invoice and its line items for a given Reservation.
    This is typically called upon check-out or when an invoice is manually requested.
    """
    if not reservation:
        raise ValueError("A valid reservation instance is required.")

    if hasattr(reservation, 'invoice') and reservation.invoice:
        # Potentially return existing invoice or raise error if already invoiced
        # For now, let's assume we can regenerate or this check is done before calling
        print(f"Reservation {reservation.id} already has an invoice: {reservation.invoice.invoice_number}")
        return reservation.invoice # Or raise Exception("Invoice already exists for this reservation.")

    if not issue_date:
        issue_date = timezone.now().date()

    calculated_due_date = issue_date + timezone.timedelta(days=due_date_days)

    with transaction.atomic():
        # Create the Invoice instance
        invoice = Invoice.objects.create(
            reservation=reservation,
            guest=reservation.guest,
            issue_date=issue_date,
            due_date=calculated_due_date,
            # tax_percentage can be from hotel settings, default is on model
            # status will default to DRAFT
        )

        # 1. Add Room Charges
        current_day = reservation.check_in_date
        while current_day < reservation.check_out_date:
            daily_rate = reservation.room.get_price_for_date(current_day)
            InvoiceLineItem.objects.create(
                invoice=invoice,
                description=f"Room Charge: {reservation.room.room_type.name} - {current_day.strftime('%Y-%m-%d')}",
                quantity=1,
                unit_price=daily_rate
            )
            current_day += timezone.timedelta(days=1)

        # 2. Add Early Check-in Fee
        if reservation.is_early_check_in_approved and reservation.early_check_in_fee and reservation.early_check_in_fee > 0:
            InvoiceLineItem.objects.create(
                invoice=invoice,
                description="Early Check-in Fee",
                quantity=1,
                unit_price=reservation.early_check_in_fee
            )

        # 3. Add Late Check-out Fee
        if reservation.is_late_check_out_approved and reservation.late_check_out_fee and reservation.late_check_out_fee > 0:
            InvoiceLineItem.objects.create(
                invoice=invoice,
                description="Late Check-out Fee",
                quantity=1,
                unit_price=reservation.late_check_out_fee
            )

        # 4. Add Billable Room Service Requests
        # Assuming RoomServiceRequest has a 'reservation' link and a 'price'
        billable_services = RoomServiceRequest.objects.filter(
            reservation=reservation,
            price__isnull=False,
            price__gt=0,
            status=RoomServiceRequest.RequestStatus.COMPLETED # Only bill completed services
        )
        for service in billable_services:
            InvoiceLineItem.objects.create(
                invoice=invoice,
                description=f"Room Service: {service.get_request_type_display()} - {service.description[:50]}", # Truncate desc
                quantity=1, # Assuming quantity is handled in service.price itself or service has quantity field
                unit_price=service.price
            )

        # After all line items are created, update invoice totals and status
        invoice.update_totals(save_instance=False) # Calculate totals
        invoice.update_status(save_instance=False) # Update status based on new totals and paid_amount (0 for now)

        # Set status to SENT if generation implies it's ready for guest
        # Or keep DRAFT for review. For now, let's assume it becomes SENT.
        if invoice.status == Invoice.InvoiceStatus.DRAFT and invoice.grand_total > 0:
             invoice.status = Invoice.InvoiceStatus.SENT

        invoice.save() # Save the invoice with all updates

    return invoice
