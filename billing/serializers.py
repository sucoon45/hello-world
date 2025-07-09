from rest_framework import serializers
from .models import Invoice, InvoiceLineItem, Payment
from reservations.serializers import GuestSerializer # To show guest details if needed

class InvoiceLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLineItem
        fields = ('id', 'description', 'quantity', 'unit_price', 'line_total')
        read_only_fields = ('line_total',) # Calculated by model

class InvoiceSerializer(serializers.ModelSerializer):
    line_items = InvoiceLineItemSerializer(many=True, read_only=True) # Read-only here, managed by service/signals
    guest_details = GuestSerializer(source='guest', read_only=True) # Optional: show guest details
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Invoice
        fields = (
            'id', 'invoice_number', 'reservation', 'guest', 'guest_details', 'issue_date', 'due_date',
            'sub_total', 'discount_amount', 'discount_reason',
            'tax_percentage', 'tax_amount', 'grand_total', 'paid_amount',
            'status', 'status_display', 'notes', 'line_items',
            'created_at', 'updated_at'
        )
        read_only_fields = (
            'invoice_number', 'sub_total', 'tax_amount', 'grand_total',
            'paid_amount', # Updated by Payments
            'status_display', 'created_at', 'updated_at'
            # 'status' can be updated by staff for certain transitions (e.g. DRAFT -> SENT, or to CANCELLED)
        )
        # `guest` and `reservation` are set at creation time by the service.
        # `issue_date`, `due_date`, `discount_amount`, `discount_reason`, `tax_percentage`, `notes`, `status` can be updatable by staff.

    # If direct creation/update of line items via InvoiceSerializer is needed (not recommended if using service for generation):
    # line_items = InvoiceLineItemSerializer(many=True, required=False)
    # def create(self, validated_data):
    #     items_data = validated_data.pop('line_items', [])
    #     invoice = Invoice.objects.create(**validated_data)
    #     for item_data in items_data:
    #         InvoiceLineItem.objects.create(invoice=invoice, **item_data)
    #     invoice.update_totals(save_instance=True)
    #     invoice.update_status(save_instance=True)
    #     return invoice
    # def update(self, instance, validated_data):
    #     # Handle line item updates if supported
    #     instance = super().update(instance, validated_data)
    #     instance.update_totals(save_instance=True) # Recalculate if discount/tax_percentage changed
    #     instance.update_status(save_instance=True)
    #     return instance


class PaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.StringRelatedField(source='invoice.invoice_number', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)

    # For creating payments, invoice ID is needed
    invoice_id = serializers.PrimaryKeyRelatedField(
        queryset=Invoice.objects.all(), source='invoice', write_only=True
    )
    # For refunds, original_payment ID might be needed
    original_payment_id = serializers.PrimaryKeyRelatedField(
        queryset=Payment.objects.filter(is_refund=False), # Only link to non-refund payments
        source='original_payment',
        write_only=True,
        required=False,
        allow_null=True
    )

    class Meta:
        model = Payment
        fields = (
            'id', 'invoice', 'invoice_id', 'invoice_number',
            'payment_date', 'amount', 'payment_method', 'payment_method_display',
            'transaction_id', 'notes', 'is_refund',
            'original_payment', 'original_payment_id',
            'created_at', 'updated_at'
        )
        read_only_fields = ('invoice', 'original_payment', 'created_at', 'updated_at')

    def validate(self, data):
        if data.get('is_refund'):
            if not data.get('original_payment') and not self.instance : # original_payment required for new refunds
                # This check might be too simple if refunds can be standalone adjustments.
                # For now, assume refund links to an original payment.
                # raise serializers.ValidationError("Original payment must be specified for refunds.")
                pass # Allowing standalone refunds for now, or refunds not directly tied to a payment.
            if data['amount'] < 0: # Ensure refund amount is positive, is_refund flag handles direction
                 data['amount'] = abs(data['amount'])
        elif data['amount'] < 0:
            raise serializers.ValidationError("Payment amount cannot be negative. Use 'is_refund' for refunds.")
        return data
