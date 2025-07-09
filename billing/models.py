from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings # For default due days setting
from decimal import Decimal
import uuid

# Function to generate a unique invoice number
def generate_invoice_number():
    date_str = timezone.now().strftime('%Y%m%d')
    unique_part = uuid.uuid4().hex[:6].upper() # Made slightly longer for more uniqueness
    return f"INV-{date_str}-{unique_part}"

class Invoice(models.Model):
    class InvoiceStatus(models.TextChoices):
        DRAFT = 'DRAFT', _('Draft')
        SENT = 'SENT', _('Sent')
        PAID = 'PAID', _('Paid')
        PARTIALLY_PAID = 'PARTIALLY_PAID', _('Partially Paid')
        OVERDUE = 'OVERDUE', _('Overdue')
        CANCELLED = 'CANCELLED', _('Cancelled')

    # Using string literal for ForeignKey to avoid circular import issues if models are split later
    reservation = models.OneToOneField(
        'reservations.Reservation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='invoice'
    )
    guest = models.ForeignKey(
        'reservations.Guest',
        on_delete=models.PROTECT,
        related_name='invoices'
    )
    invoice_number = models.CharField(max_length=50, unique=True, default=generate_invoice_number, editable=False)
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField()

    sub_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), editable=False)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_reason = models.CharField(max_length=255, blank=True, null=True)

    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text="Tax rate (e.g., 10 for 10%). Set to 0 if no tax.")
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), editable=False)

    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), editable=False)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    status = models.CharField(max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT)
    notes = models.TextField(blank=True, null=True, help_text="Internal notes or notes for the guest on the invoice.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-issue_date', '-invoice_number']

    def __str__(self):
        return f"Invoice {self.invoice_number} for {self.guest}"

    def _calculate_sub_total_from_items(self):
        return sum(item.line_total for item in self.line_items.all()) if self.pk else Decimal('0.00')

    def _calculate_tax_amount(self, sub_total_after_discount):
        if self.tax_percentage > 0:
            return (sub_total_after_discount * self.tax_percentage) / Decimal('100')
        return Decimal('0.00')

    def update_totals(self, save_instance=True):
        """Recalculates sub_total, tax_amount, and grand_total based on line items and discount."""
        self.sub_total = self._calculate_sub_total_from_items()

        sub_total_after_discount = self.sub_total - self.discount_amount
        # Ensure discount doesn't make the effective subtotal negative
        sub_total_after_discount = max(Decimal('0.00'), sub_total_after_discount)

        self.tax_amount = self._calculate_tax_amount(sub_total_after_discount)
        self.grand_total = sub_total_after_discount + self.tax_amount

        if save_instance:
            self.save(update_fields=['sub_total', 'tax_amount', 'grand_total'])

    def update_status(self, save_instance=True):
        """Updates the invoice status based on paid_amount, grand_total, and due_date."""
        if self.status == self.InvoiceStatus.CANCELLED: # Cancelled invoices don't change status unless un-cancelled
            if save_instance: self.save(update_fields=['status'])
            return

        if self.grand_total <= Decimal('0.00') and self.paid_amount <= Decimal('0.00'): # Effectively a zero invoice or fully comped
             self.status = self.InvoiceStatus.PAID # Or a 'COMPED' status if preferred
        elif self.paid_amount >= self.grand_total:
            self.status = self.InvoiceStatus.PAID
        elif self.paid_amount > Decimal('0.00'):
            self.status = self.InvoiceStatus.PARTIALLY_PAID
        elif self.due_date < timezone.now().date(): # Assuming status is not DRAFT or PAID/PARTIALLY_PAID
            self.status = self.InvoiceStatus.OVERDUE
        elif self.status == self.InvoiceStatus.OVERDUE and self.due_date >= timezone.now().date(): # If due date changed or was wrong
             self.status = self.InvoiceStatus.SENT # Or DRAFT if not yet sent
        # Default to DRAFT if no other condition met and not already PAID/PARTIALLY_PAID
        # This part needs care to not override SENT status if still unpaid but not overdue.
        # Let's assume if it's not PAID or PARTIALLY_PAID, and not OVERDUE, it's either DRAFT or SENT.
        # The transition from DRAFT to SENT is an explicit action.

        if save_instance:
            self.save(update_fields=['status'])


    def save(self, *args, **kwargs):
        if not self.due_date and self.issue_date:
            default_due_days = getattr(settings, 'DEFAULT_INVOICE_DUE_DAYS', 15)
            self.due_date = self.issue_date + timezone.timedelta(days=default_due_days)

        # Note: update_totals() and update_status() are generally called explicitly
        # after line items or payments change, or when invoice is first generated.
        # Avoid calling them unconditionally here to prevent recursion if they also call save().
        super().save(*args, **kwargs)


class InvoiceLineItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='line_items')
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2, editable=False)

    def __str__(self):
        return f"{self.description} (x{self.quantity}) for Invoice {self.invoice.invoice_number}"

    def save(self, *args, **kwargs):
        self.line_total = self.quantity * self.unit_price
        super().save(*args, **kwargs)
        # Signal or explicit call to invoice.update_totals() is better here
        # self.invoice.update_totals(save_instance=True) # This can cause issues if called during Invoice.save()

    def delete(self, *args, **kwargs):
        # Signal or explicit call to invoice.update_totals() is better
        # invoice = self.invoice
        super().delete(*args, **kwargs)
        # invoice.update_totals(save_instance=True)


class Payment(models.Model):
    class PaymentMethod(models.TextChoices):
        CARD = 'CARD', _('Card')
        CASH = 'CASH', _('Cash')
        ONLINE_GATEWAY = 'ONLINE_GATEWAY', _('Online Gateway')
        BANK_TRANSFER = 'BANK_TRANSFER', _('Bank Transfer')
        OTHER = 'OTHER', _('Other')

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    payment_date = models.DateTimeField(default=timezone.now)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CARD)
    transaction_id = models.CharField(max_length=255, blank=True, null=True, help_text="External transaction ID, e.g., from payment gateway.")
    notes = models.TextField(blank=True, null=True)

    is_refund = models.BooleanField(default=False)
    # If is_refund is True, this can link to the original payment being refunded.
    # For simplicity, a negative amount could also signify a refund, but is_refund is clearer.
    original_payment = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='refunds',
        help_text="Link to the original payment if this is a refund transaction."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        type_str = "Refund" if self.is_refund else "Payment"
        return f"{type_str} of {self.amount} for Invoice {self.invoice.invoice_number} via {self.get_payment_method_display()}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # After saving a payment, update the parent invoice's paid_amount and status
        # This is a good candidate for a signal handler as well.

        # Recalculate invoice's paid_amount
        current_paid_amount = Decimal('0.00')
        for pmt in self.invoice.payments.all():
            if pmt.is_refund:
                current_paid_amount -= pmt.amount
            else:
                current_paid_amount += pmt.amount

        self.invoice.paid_amount = current_paid_amount
        self.invoice.update_status(save_instance=True) # update_status will also save the invoice

    # Consider what happens on delete - invoice paid_amount needs recalculation.
    # A signal on delete of Payment would be appropriate.
