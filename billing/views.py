from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend # Ensure this is installed
from rest_framework import filters
from django.utils import timezone
from decimal import Decimal # For perform_destroy calculation

from .models import Invoice, Payment, InvoiceLineItem # InvoiceLineItem might not be directly exposed via ViewSet
from .serializers import InvoiceSerializer, PaymentSerializer
from users.models import CustomUser # For permission checks
# from .services import generate_invoice_for_reservation # If manual generation via API is needed

# Placeholder permissions (define these properly in a permissions.py)
class IsAdminOrAccounting(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in [CustomUser.Role.ADMIN, CustomUser.Role.ACCOUNTING]

class CanRecordPayment(permissions.BasePermission): # Admin, Accounting, FrontDesk
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in [CustomUser.Role.ADMIN, CustomUser.Role.ACCOUNTING, CustomUser.Role.FRONT_DESK]


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all().select_related('guest', 'reservation').prefetch_related('line_items', 'payments')
    serializer_class = InvoiceSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'guest__id': ['exact'],
        'reservation__id': ['exact'],
        'status': ['exact', 'in'],
        'issue_date': ['exact', 'gte', 'lte', 'range'], # Added 'range'
        'due_date': ['exact', 'gte', 'lte', 'range'],   # Added 'range'
        'grand_total': ['exact', 'gte', 'lte'],
    }
    search_fields = ['invoice_number', 'guest__first_name', 'guest__last_name', 'guest__email']
    ordering_fields = ['issue_date', 'due_date', 'grand_total', 'status']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            # Allow guests to see their own invoices, staff to see all
            return [permissions.IsAuthenticated()]
        if self.action in ['update', 'partial_update']: # e.g. change status, add discount
            return [IsAdminOrAccounting()]
        if self.action == 'destroy': # Voiding/Cancelling might be better via status change (e.g. set status to CANCELLED)
            return [permissions.IsAdminUser()]
        if self.action == 'create': # Manual invoice creation
            return [IsAdminOrAccounting()]
        if self.action == 'send_invoice': # Custom action
            return [IsAdminOrAccounting()]
        return super().get_permissions() # Should default to IsAdminUser or similar strict permission

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()
        if not user.is_authenticated:
            return queryset.none()
        if user.role in [CustomUser.Role.ADMIN, CustomUser.Role.ACCOUNTING, CustomUser.Role.FRONT_DESK]:
            return queryset
        if hasattr(user, 'guest_profile') and user.guest_profile: # Check if guest_profile exists
            return queryset.filter(guest=user.guest_profile)
        return queryset.none() # Should not be reachable for authenticated users if roles cover all staff

    def perform_create(self, serializer):
        # Manual invoice creation - ensure guest is set.
        # Reservation can be null for miscellaneous invoices.
        # Totals should be calculated after line items (if any are passed through serializer) are added.
        # For now, assume line items are managed separately or by the generation service.
        invoice = serializer.save()
        # If creating manually and line_items could be part of request:
        # invoice.update_totals(save_instance=False)
        # invoice.update_status(save_instance=True)
        # For now, just save. Totals will be 0 until line items added or service runs.
        # Default due_date is handled by model's save if not provided.

    def perform_update(self, serializer):
        invoice = serializer.save()
        # If discount, tax_percentage might change, or if line items were editable via serializer.
        # Call update_totals and update_status to ensure consistency.
        invoice.update_totals(save_instance=False)
        invoice.update_status(save_instance=True) # This save will commit changes from update_totals as well

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrAccounting])
    def send_invoice(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status == Invoice.InvoiceStatus.DRAFT:
            invoice.status = Invoice.InvoiceStatus.SENT
            if not invoice.issue_date: # Set issue date if not already set
                 invoice.issue_date = timezone.now().date()
            # Recalculate due_date based on new issue_date if it makes sense for workflow
            # default_due_days = getattr(settings, 'DEFAULT_INVOICE_DUE_DAYS', 15)
            # invoice.due_date = invoice.issue_date + timezone.timedelta(days=default_due_days)
            invoice.save(update_fields=['status', 'issue_date']) # Add 'due_date' if it's updated

            # TODO: Add actual email sending logic here
            # from .email_utils import send_invoice_email (create this utility in billing app)
            # send_invoice_email(invoice)

            return Response({'status': 'Invoice marked as SENT.'}, status=status.HTTP_200_OK) # Removed "queued for email" for now
        elif invoice.status == Invoice.InvoiceStatus.SENT:
            return Response({'status': 'Invoice already sent.'}, status=status.HTTP_200_OK)
        return Response({'error': f'Invoice in {invoice.get_status_display()} status cannot be sent.'}, status=status.HTTP_400_BAD_REQUEST)


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all().select_related('invoice', 'invoice__guest', 'original_payment')
    serializer_class = PaymentSerializer
    permission_classes = [CanRecordPayment]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter] # Removed SearchFilter as less common for payments directly
    filterset_fields = {
        'invoice__id': ['exact'],
        'invoice__invoice_number': ['exact'], # Filter by invoice number
        'payment_date': ['exact', 'gte', 'lte', 'range'],
        'payment_method': ['exact', 'in'],
        'is_refund': ['exact'],
        'transaction_id': ['exact', 'icontains'],
    }
    ordering_fields = ['payment_date', 'amount']

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Payment.objects.none()

        if user.role in [CustomUser.Role.ADMIN, CustomUser.Role.ACCOUNTING, CustomUser.Role.FRONT_DESK]:
            invoice_pk = self.kwargs.get('invoice_pk') # For nested URL: /invoices/{invoice_pk}/payments/
            if invoice_pk:
                return super().get_queryset().filter(invoice_id=invoice_pk)
            return super().get_queryset()
        return Payment.objects.none() # Guests don't typically access raw payment records this way

    def perform_create(self, serializer):
        # Invoice paid_amount and status are updated by Payment model's save() method signal or direct call.
        invoice_pk = self.kwargs.get('invoice_pk')
        invoice_instance = serializer.validated_data.get('invoice') # From invoice_id field

        if invoice_pk and not invoice_instance: # If nested URL used but invoice_id not in payload
            try:
                invoice_instance = Invoice.objects.get(pk=invoice_pk)
                serializer.save(invoice=invoice_instance)
            except Invoice.DoesNotExist:
                raise serializers.ValidationError({"invoice_id": "Invalid Invoice ID in URL."})
        elif invoice_instance: # If invoice_id was in payload
             serializer.save() # invoice is already set by serializer
        else: # Should not happen if invoice_id is required=True in serializer
            raise serializers.ValidationError({"invoice_id": "Invoice ID is required."})

    def perform_destroy(self, instance):
        # Store invoice before deleting payment to update it afterwards
        invoice_to_update = instance.invoice
        super().perform_destroy(instance)

        # Recalculate invoice's paid_amount after payment deletion
        current_paid_amount = Decimal('0.00')
        for pmt in invoice_to_update.payments.all(): # Query again as instance is deleted from queryset
            if pmt.is_refund:
                current_paid_amount -= pmt.amount
            else:
                current_paid_amount += pmt.amount
        invoice_to_update.paid_amount = current_paid_amount
        # update_status will also call save on the invoice
        invoice_to_update.update_status(save_instance=True)
