
# ---------------------------
# payments/models.py
# ---------------------------
from django.db import models
from django.conf import settings
from django.utils import timezone

# If your orders app is in a separate app, import lazily to avoid circular imports in some setups
# from orders.models import Order


class Payment(models.Model):
    """Represents a payment attempt or completed payment for an order.

    Designed to support M-Pesa Daraja STK Push flow and other payment providers.
    """
    STATUS_PENDING = 'pending'
    STATUS_INITIATED = 'initiated'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_INITIATED, 'Initiated'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    order_id = models.PositiveIntegerField(null=True, blank=True, help_text='Optional: link to Order PK if Order model is in another app')
    # If you prefer a direct FK, use: order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True)

    provider = models.CharField(max_length=50, default='mpesa')
    provider_reference = models.CharField(max_length=255, blank=True, db_index=True, help_text='Reference returned by provider (CheckoutRequestID / TransactionID)')

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default='KES')
    phone_number = models.CharField(max_length=32, help_text='Phone used for payment (e.g., 2547...)')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    initiated_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    raw_payload = models.JSONField(blank=True, null=True, help_text='Full provider response payload for debugging/audit')
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['provider_reference']), models.Index(fields=['user', 'status'])]

    def __str__(self):
        return f"Payment({self.id}) {self.amount} {self.currency} - {self.status}"

    def mark_initiated(self, provider_reference: str = None):
        self.status = self.STATUS_INITIATED
        if provider_reference:
            self.provider_reference = provider_reference
        self.initiated_at = timezone.now()
        self.save(update_fields=['status', 'provider_reference', 'initiated_at', 'updated_at'])

    def mark_success(self, payload: dict = None):
        self.status = self.STATUS_SUCCESS
        self.completed_at = timezone.now()
        if payload:
            # Merge M-Pesa response with existing payload, preserving original metadata
            if self.raw_payload and isinstance(self.raw_payload, dict):
                self.raw_payload.update({'mpesa_response': payload})
            else:
                self.raw_payload = {'mpesa_response': payload}
        self.save(update_fields=['status', 'completed_at', 'raw_payload', 'updated_at'])

    def mark_failed(self, payload: dict = None, note: str = ''):
        self.status = self.STATUS_FAILED
        self.completed_at = timezone.now()
        if payload:
            # Merge M-Pesa response with existing payload, preserving original metadata
            if self.raw_payload and isinstance(self.raw_payload, dict):
                self.raw_payload.update({'mpesa_response': payload})
            else:
                self.raw_payload = {'mpesa_response': payload}
        if note:
            self.notes = (self.notes + "\n" + note).strip()
        self.save(update_fields=['status', 'completed_at', 'raw_payload', 'notes', 'updated_at'])


class BNPLUser(models.Model):
    """Tracks users who have opted in for Buy Now, Pay Later."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bnpl')
    is_active = models.BooleanField(default=True)
    phone_number = models.CharField(max_length=32)
    credit_limit = models.DecimalField(max_digits=10, decimal_places=2, default=5000.00)
    current_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"BNPL - {self.user.username}"

    class Meta:
        verbose_name = "BNPL User"
        verbose_name_plural = "BNPL Users"


class MpesaSTKRequest(models.Model):
    """Tracks an STK Push request lifecycle with Daraja (M-Pesa).

    - `checkout_request_id` is returned when initiating the STK push and used to query status.
    - `merchant_request_id` / `checkout_request_id` / `result_code` fields store Daraja responses.
    """
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='stk_requests')

    checkout_request_id = models.CharField(max_length=255, blank=True, db_index=True)
    merchant_request_id = models.CharField(max_length=255, blank=True, db_index=True)
    result_code = models.IntegerField(null=True, blank=True)
    result_desc = models.TextField(blank=True)

    callback_payload = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['checkout_request_id']), models.Index(fields=['merchant_request_id'])]

    def __str__(self):
        return f"MpesaSTKRequest({self.id}) for Payment {self.payment_id}"


# End of file


class TradeIn(models.Model):
    """Stores user-submitted trade-in items for evaluation."""
    STATUS_PENDING = 'pending'
    STATUS_RECEIVED = 'received'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_RECEIVED, 'Received'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tradeins')
    description = models.TextField(help_text='Description of the item being traded in')
    estimated_price = models.DecimalField(max_digits=10, decimal_places=2)
    contact_phone = models.CharField(max_length=32, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"TradeIn({self.id}) {self.user} - {self.status}"

