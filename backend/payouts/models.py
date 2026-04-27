import uuid
from datetime import timedelta

from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone


class Merchant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    bank_accounts = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_balance(self):
        """
        Balance ALWAYS derived from DB aggregate, never stored separately.
        Returns: (available_paise, held_paise)
          available_paise = sum(CREDIT) - sum(DEBIT)  [reflects committed ledger]
          held_paise      = sum(DEBIT) for payouts in PENDING / PROCESSING
        """
        agg = LedgerEntry.objects.filter(merchant=self).aggregate(
            credits=Sum('amount', filter=Q(entry_type='CREDIT')),
            debits=Sum('amount', filter=Q(entry_type='DEBIT')),
        )
        credits = agg['credits'] or 0
        debits = agg['debits'] or 0
        available = credits - debits

        held = LedgerEntry.objects.filter(
            merchant=self,
            entry_type='DEBIT',
            payout__status__in=['PENDING', 'PROCESSING'],
        ).aggregate(total=Sum('amount'))['total'] or 0

        return available, held

    def __str__(self):
        return self.name


class Payout(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    LEGAL_TRANSITIONS = {
        'PENDING': ['PROCESSING'],
        'PROCESSING': ['COMPLETED', 'FAILED'],
        'COMPLETED': [],
        'FAILED': [],
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.PROTECT, related_name='payouts'
    )
    amount_paise = models.BigIntegerField()
    bank_account_id = models.CharField(max_length=100)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='PENDING'
    )
    idempotency_key = models.CharField(max_length=255)
    attempts = models.IntegerField(default=0)
    last_attempted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('merchant', 'idempotency_key')]
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['merchant', 'idempotency_key']),
        ]

    def transition_to(self, new_status):
        """The ONLY way to change status. Illegal transitions raise ValueError."""
        legal = self.LEGAL_TRANSITIONS.get(self.status, [])
        if new_status not in legal:
            raise ValueError(
                f"Illegal transition: {self.status} → {new_status}. Legal: {legal}"
            )
        self.status = new_status

    def __str__(self):
        return f"Payout {self.id} — {self.status} — {self.amount_paise}p"


class LedgerEntry(models.Model):
    ENTRY_TYPES = [('CREDIT', 'Credit'), ('DEBIT', 'Debit')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.PROTECT, related_name='ledger_entries'
    )
    amount = models.BigIntegerField()
    entry_type = models.CharField(max_length=6, choices=ENTRY_TYPES)
    description = models.CharField(max_length=255)
    payout = models.ForeignKey(
        Payout,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ledger_entries',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['merchant', 'entry_type']),
        ]

    def __str__(self):
        return f"{self.entry_type} {self.amount}p — {self.merchant.name}"


class IdempotencyKey(models.Model):
    """Stores idempotency keys with their cached response. Scoped per merchant."""
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE)
    key = models.CharField(max_length=255)
    response_body = models.JSONField()
    response_status = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('merchant', 'key')]
        indexes = [models.Index(fields=['created_at'])]

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(hours=24)
