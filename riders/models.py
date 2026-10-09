"""
Combined models.py content for two Django apps: `riders` and `payments`.

Save the `riders` portion to `riders/models.py` and the `payments` portion to `payments/models.py` in your project.

These models assume you have a custom user model (settings.AUTH_USER_MODEL) and an `orders.Order` model.
"""

# ---------------------------
# riders/models.py
# ---------------------------
from django.conf import settings
from django.db import models
from django.utils import timezone
import uuid


class RiderProfile(models.Model):
    """Optional extended profile for users that act as riders/drivers.

    If you already store rider fields on your custom User model (is_rider flag),
    you can use this profile for extra per-rider data (vehicle, documents, rating).
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rider_profile')
    display_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    vehicle_type = models.CharField(max_length=60, blank=True, help_text='e.g. Motorcycle, Car, Van')
    vehicle_reg = models.CharField(max_length=40, blank=True, help_text='Vehicle registration number')
    is_active = models.BooleanField(default=True)

    # verification / docs
    id_document = models.FileField(upload_to='riders/docs/', blank=True, null=True)
    license_document = models.FileField(upload_to='riders/docs/', blank=True, null=True)

    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    completed_jobs = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Rider profile'
        verbose_name_plural = 'Rider profiles'

    def __str__(self):
        return self.display_name or getattr(self.user, 'username', str(self.user))


class RiderLocation(models.Model):
    """Stores periodic location updates from riders for live tracking.

    A rider device (mobile app) should POST GPS updates to an endpoint that
    creates RiderLocation rows. For real-time apps you can combine this with
    Django Channels / Redis to broadcast locations.
    """
    rider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='locations')
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    accuracy = models.FloatField(blank=True, null=True, help_text='GPS accuracy in meters')
    heading = models.FloatField(blank=True, null=True, help_text='Direction in degrees')
    speed = models.FloatField(blank=True, null=True, help_text='Speed in m/s')

    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']
        indexes = [models.Index(fields=['rider', 'recorded_at'])]

    def __str__(self):
        return f"{self.rider} @ {self.latitude},{self.longitude} ({self.recorded_at.isoformat()})"


class RiderWallet(models.Model):
    """Available payout balance and M-Pesa destination for one rider."""
    rider = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='rider_wallet',
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payout_phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Rider wallet - {self.rider} (KES {self.balance})"


class RiderWalletTransaction(models.Model):
    """Immutable audit entries for credits, withdrawals, and withdrawal reversals."""
    TYPE_CREDIT = 'credit'
    TYPE_WITHDRAWAL = 'withdrawal'
    TYPE_REVERSAL = 'reversal'
    TYPE_CHOICES = [
        (TYPE_CREDIT, 'Admin credit'),
        (TYPE_WITHDRAWAL, 'Withdrawal'),
        (TYPE_REVERSAL, 'Withdrawal reversal'),
    ]
    STATUS_COMPLETED = 'completed'
    STATUS_PENDING = 'pending'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_FAILED, 'Failed'),
    ]

    wallet = models.ForeignKey(RiderWallet, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_COMPLETED)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    reason = models.TextField(blank=True)
    payout_phone = models.CharField(max_length=20, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rider_wallet_actions',
    )
    conversation_id = models.CharField(max_length=100, blank=True, db_index=True)
    originator_conversation_id = models.CharField(max_length=100, blank=True, db_index=True)
    provider_transaction_id = models.CharField(max_length=100, blank=True)
    provider_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['wallet', '-created_at'])]

    def __str__(self):
        return f"{self.transaction_type} {self.amount} KES ({self.status})"


class WasherWallet(models.Model):
    """Available payout balance and M-Pesa destination for one washer."""
    washer = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='washer_wallet',
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payout_phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Washer wallet - {self.washer} (KES {self.balance})"


class WasherWalletTransaction(models.Model):
    """Immutable audit entries for washer credits, withdrawals and reversals."""
    TYPE_CREDIT = 'credit'
    TYPE_WITHDRAWAL = 'withdrawal'
    TYPE_REVERSAL = 'reversal'
    TYPE_CHOICES = [
        (TYPE_CREDIT, 'Admin credit'),
        (TYPE_WITHDRAWAL, 'Withdrawal'),
        (TYPE_REVERSAL, 'Withdrawal reversal'),
    ]
    STATUS_COMPLETED = 'completed'
    STATUS_PENDING = 'pending'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_FAILED, 'Failed'),
    ]

    wallet = models.ForeignKey(WasherWallet, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_COMPLETED)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    reason = models.TextField(blank=True)
    payout_phone = models.CharField(max_length=20, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='washer_wallet_actions',
    )
    conversation_id = models.CharField(max_length=100, blank=True, db_index=True)
    originator_conversation_id = models.CharField(max_length=100, blank=True, db_index=True)
    provider_transaction_id = models.CharField(max_length=100, blank=True)
    provider_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['wallet', '-created_at'])]

    def __str__(self):
        return f"Washer {self.transaction_type} {self.amount} KES ({self.status})"

