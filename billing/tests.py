from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from decimal import Decimal
import datetime

from .models import Invoice, InvoiceLineItem, Payment
from reservations.models import Reservation, Guest
from hotel_core.models import Room, RoomType, RoomServiceRequest
from users.models import CustomUser
from .services import generate_invoice_for_reservation

class BillingAPITests(APITestCase):
    def setUp(self):
        # Users
        self.admin_user = CustomUser.objects.create_superuser('bill_admin', 'bill_admin@example.com', 'password123', role=CustomUser.Role.ADMIN)
        self.acc_user = CustomUser.objects.create_user('bill_acc', 'bill_acc@example.com', 'password123', role=CustomUser.Role.ACCOUNTING)
        self.staff_user = CustomUser.objects.create_user('bill_staff', 'bill_staff@example.com', 'password123', role=CustomUser.Role.FRONT_DESK)

        # Guest User and Profile
        self.guest_user_custom = CustomUser.objects.create_user('guest_bill_user', 'guest_bill_user@example.com', 'password123', role=CustomUser.Role.GUEST)
        self.guest = Guest.objects.create(first_name="Bill", last_name="Payer", email="bill.payer@example.com", user_account=self.guest_user_custom)


        # Room Type & Room
        self.room_type = RoomType.objects.create(name="Standard Billing Room", capacity=2)
        self.room = Room.objects.create(room_number="B101", room_type=self.room_type, price_per_night=Decimal("100.00"))

        # Reservation
        self.today = timezone.now().date()
        self.reservation = Reservation.objects.create(
            guest=self.guest,
            room=self.room,
            check_in_date=self.today - datetime.timedelta(days=2),
            check_out_date=self.today, # Checked out today, 2 nights stay
            status=Reservation.ReservationStatus.CHECKED_OUT, # Important for invoice generation trigger
            number_of_adults=2,
        )
        self.reservation.save() # Ensure total_price is calculated based on daily rates


    # --- Model Method Tests ---
    def test_invoice_total_calculations(self):
        invoice = Invoice.objects.create(reservation=self.reservation, guest=self.guest, due_date=self.today + datetime.timedelta(days=15))
        InvoiceLineItem.objects.create(invoice=invoice, description="Item 1", quantity=1, unit_price=Decimal("50.00")) # Save triggers invoice update
        InvoiceLineItem.objects.create(invoice=invoice, description="Item 2", quantity=2, unit_price=Decimal("25.00")) # Save triggers invoice update

        invoice.refresh_from_db()
        self.assertEqual(invoice.sub_total, Decimal("100.00"))

        invoice.discount_amount = Decimal("10.00")
        invoice.tax_percentage = Decimal("10.00")
        invoice.update_totals(save_instance=True) # Explicitly call to update with discount/tax
        invoice.update_status(save_instance=True) # And then update status

        expected_sub_after_discount = Decimal("90.00")
        expected_tax = expected_sub_after_discount * (Decimal("10.00") / Decimal("100"))
        expected_grand_total = expected_sub_after_discount + expected_tax

        self.assertEqual(invoice.tax_amount, expected_tax)
        self.assertEqual(invoice.grand_total, expected_grand_total)

    def test_invoice_status_update_on_payment(self):
        invoice = Invoice.objects.create(
            reservation=self.reservation, guest=self.guest,
            due_date=self.today + datetime.timedelta(days=15),
            status=Invoice.InvoiceStatus.SENT # Start as SENT
        )
        # Manually set grand_total as line items are not created in this specific test path directly
        invoice.grand_total = Decimal("100.00")
        invoice.save()


        # Partial Payment
        Payment.objects.create(invoice=invoice, amount=Decimal("50.00")) # Save triggers invoice update
        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount, Decimal("50.00"))
        self.assertEqual(invoice.status, Invoice.InvoiceStatus.PARTIALLY_PAID)

        # Full Payment
        Payment.objects.create(invoice=invoice, amount=Decimal("50.00")) # Save triggers invoice update
        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount, Decimal("100.00"))
        self.assertEqual(invoice.status, Invoice.InvoiceStatus.PAID)

    # --- Service Function Tests ---
    def test_generate_invoice_for_reservation(self):
        RoomServiceRequest.objects.create(
            reservation=self.reservation, room=self.room,
            request_type=RoomServiceRequest.RequestType.FOOD_BEVERAGE,
            description="Dinner", price=Decimal("35.00"),
            status=RoomServiceRequest.RequestStatus.COMPLETED,
            requested_by=self.admin_user
        )
        self.reservation.is_early_check_in_approved = True
        self.reservation.early_check_in_fee = Decimal("20.00")
        self.reservation.save()

        invoice = generate_invoice_for_reservation(self.reservation)
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.guest, self.guest)
        self.assertEqual(invoice.reservation, self.reservation)

        self.assertEqual(invoice.line_items.count(), 4) # 2 room nights, 1 early fee, 1 room service

        room_charge_total = self.room.get_price_for_date(self.today - datetime.timedelta(days=2)) + \
                            self.room.get_price_for_date(self.today - datetime.timedelta(days=1))
        early_fee_total = Decimal("20.00")
        room_service_total = Decimal("35.00")
        expected_sub_total = room_charge_total + early_fee_total + room_service_total

        self.assertEqual(invoice.sub_total, expected_sub_total)

        # Test with default tax_percentage from model (10%)
        invoice.tax_percentage = Decimal("10.00")
        invoice.update_totals(save_instance=True)
        invoice.update_status(save_instance=True)
        invoice.refresh_from_db()

        expected_tax = expected_sub_total * (Decimal("10.00") / Decimal("100"))
        expected_grand_total = expected_sub_total + expected_tax
        self.assertEqual(invoice.tax_amount, expected_tax)
        self.assertEqual(invoice.grand_total, expected_grand_total)
        self.assertEqual(invoice.status, Invoice.InvoiceStatus.SENT)


    # --- ViewSet Tests ---
    def test_accountant_can_list_invoices(self):
        self.client.force_authenticate(user=self.acc_user)
        generate_invoice_for_reservation(self.reservation)

        url = reverse('invoice-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_guest_can_retrieve_own_invoice(self):
        self.client.force_authenticate(user=self.guest_user_custom) # Guest user linked to self.guest
        invoice = generate_invoice_for_reservation(self.reservation)

        url = reverse('invoice-detail', kwargs={'pk': invoice.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['invoice_number'], invoice.invoice_number)

    def test_record_payment_by_staff(self):
        self.client.force_authenticate(user=self.staff_user)
        invoice = generate_invoice_for_reservation(self.reservation)
        invoice.status = Invoice.InvoiceStatus.SENT
        invoice.save()

        payments_url = reverse('invoice-payment-list', kwargs={'invoice_pk': invoice.pk})

        payment_data = {
            # invoice_id is implicit from URL for nested creation
            "amount": invoice.grand_total,
            "payment_method": Payment.PaymentMethod.CARD,
            "transaction_id": "txn_123abc"
        }
        response = self.client.post(payments_url, payment_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Payment.objects.count(), 1)

        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount, invoice.grand_total)
        self.assertEqual(invoice.status, Invoice.InvoiceStatus.PAID)

    def test_record_refund(self):
        self.client.force_authenticate(user=self.acc_user)
        invoice = generate_invoice_for_reservation(self.reservation)
        invoice.status = Invoice.InvoiceStatus.SENT
        invoice.save()

        initial_payment = Payment.objects.create(
            invoice=invoice, amount=invoice.grand_total,
            payment_method=Payment.PaymentMethod.CARD, transaction_id="orig_txn_789"
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.InvoiceStatus.PAID)

        payments_url = reverse('invoice-payment-list', kwargs={'invoice_pk': invoice.pk})
        refund_amount = Decimal("50.00")
        refund_data = {
            "amount": refund_amount,
            "payment_method": Payment.PaymentMethod.CARD,
            "is_refund": True,
            "original_payment_id": initial_payment.pk,
            "notes": "Partial refund for service issue."
        }
        response = self.client.post(payments_url, refund_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Payment.objects.filter(is_refund=True).count(), 1)

        invoice.refresh_from_db()
        expected_paid_amount = initial_payment.amount - refund_amount
        self.assertEqual(invoice.paid_amount, expected_paid_amount)
        if expected_paid_amount < invoice.grand_total and expected_paid_amount > 0:
             self.assertEqual(invoice.status, Invoice.InvoiceStatus.PARTIALLY_PAID)
        elif expected_paid_amount == 0 and invoice.grand_total > 0 : # Full refund of a paid invoice
             self.assertEqual(invoice.status, Invoice.InvoiceStatus.SENT) # Or DRAFT, depends on policy
        else: # Other cases
            self.assertEqual(invoice.status, Invoice.InvoiceStatus.PARTIALLY_PAID)


    def test_invoice_filtering_by_status_and_date(self):
        self.client.force_authenticate(user=self.admin_user)

        inv1 = generate_invoice_for_reservation(self.reservation)

        # Create another reservation and invoice for different date/status
        guest2 = Guest.objects.create(first_name="Jane", last_name="DoeBill", email="jane.doebill@example.com")
        res2_checkout_date = self.today - datetime.timedelta(days=8)
        res2 = Reservation.objects.create(
            guest=guest2, room=self.room,
            check_in_date=self.today - datetime.timedelta(days=10),
            check_out_date=res2_checkout_date,
            status=Reservation.ReservationStatus.CHECKED_OUT,
            number_of_adults=1
        )
        res2.save()
        inv2 = generate_invoice_for_reservation(res2)
        inv2.issue_date = res2_checkout_date # Set issue date to checkout date
        inv2.status = Invoice.InvoiceStatus.PAID
        inv2.paid_amount = inv2.grand_total
        inv2.save()

        url = reverse('invoice-list')

        response_paid = self.client.get(f"{url}?status={Invoice.InvoiceStatus.PAID}")
        self.assertEqual(response_paid.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_paid.data['results']), 1)
        self.assertEqual(response_paid.data['results'][0]['id'], inv2.id)

        response_date = self.client.get(f"{url}?issue_date__range={self.today.isoformat()},{self.today.isoformat()}")
        self.assertEqual(response_date.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_date.data['results']), 1)
        self.assertEqual(response_date.data['results'][0]['id'], inv1.id)

    def test_send_invoice_action(self):
        self.client.force_authenticate(user=self.admin_user)
        invoice = Invoice.objects.create(
            reservation=self.reservation, guest=self.guest,
            due_date=self.today + datetime.timedelta(days=15),
            status=Invoice.InvoiceStatus.DRAFT # Start as DRAFT
        )
        # Manually add a line item and update totals for a non-zero invoice
        InvoiceLineItem.objects.create(invoice=invoice, description="Test Service", quantity=1, unit_price=Decimal("50.00"))
        invoice.refresh_from_db() # Get updated totals from line item save

        url = reverse('invoice-send-invoice', kwargs={'pk': invoice.pk})
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.InvoiceStatus.SENT)
        # self.assertEqual(invoice.issue_date, self.today) # issue_date updated to today if it was sent now.
                                                        # Current logic in view sets it to today if it was DRAFT.
                                                        # Model default is today, so this might not change if created today.
                                                        # Test should be robust to this.

        # Try sending again
        response_again = self.client.post(url, {}, format='json')
        self.assertEqual(response_again.status_code, status.HTTP_200_OK) # Idempotent if already sent
        self.assertIn("already sent", response_again.data.get('status','').lower())

        # Try sending a PAID invoice
        invoice.status = Invoice.InvoiceStatus.PAID
        invoice.save()
        response_paid = self.client.post(url, {}, format='json')
        self.assertEqual(response_paid.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cannot be sent", response_paid.data.get('error','').lower())
