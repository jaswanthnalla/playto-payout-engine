from django.db.models import Q, Sum
from rest_framework import serializers

from .models import LedgerEntry, Merchant, Payout


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = ['id', 'amount', 'entry_type', 'description', 'created_at']


class PayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = [
            'id', 'amount_paise', 'bank_account_id', 'status',
            'attempts', 'created_at', 'updated_at',
        ]


class MerchantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Merchant
        fields = ['id', 'name', 'email', 'bank_accounts']


class MerchantDashboardSerializer(serializers.ModelSerializer):
    available_balance_paise = serializers.SerializerMethodField()
    held_balance_paise = serializers.SerializerMethodField()
    recent_entries = serializers.SerializerMethodField()
    recent_payouts = serializers.SerializerMethodField()

    class Meta:
        model = Merchant
        fields = [
            'id', 'name', 'email', 'bank_accounts',
            'available_balance_paise', 'held_balance_paise',
            'recent_entries', 'recent_payouts',
        ]

    def get_available_balance_paise(self, obj):
        agg = LedgerEntry.objects.filter(merchant=obj).aggregate(
            credits=Sum('amount', filter=Q(entry_type='CREDIT')),
            debits=Sum('amount', filter=Q(entry_type='DEBIT')),
        )
        return (agg['credits'] or 0) - (agg['debits'] or 0)

    def get_held_balance_paise(self, obj):
        return LedgerEntry.objects.filter(
            merchant=obj,
            entry_type='DEBIT',
            payout__status__in=['PENDING', 'PROCESSING'],
        ).aggregate(total=Sum('amount'))['total'] or 0

    def get_recent_entries(self, obj):
        entries = obj.ledger_entries.all()[:20]
        return LedgerEntrySerializer(entries, many=True).data

    def get_recent_payouts(self, obj):
        payouts = obj.payouts.all().order_by('-created_at')[:20]
        return PayoutSerializer(payouts, many=True).data
