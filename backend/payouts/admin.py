from django.contrib import admin

from .models import IdempotencyKey, LedgerEntry, Merchant, Payout


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'created_at']
    search_fields = ['name', 'email']


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ['id', 'merchant', 'amount_paise', 'status', 'attempts', 'created_at']
    list_filter = ['status']
    search_fields = ['id', 'merchant__name', 'idempotency_key']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ['id', 'merchant', 'entry_type', 'amount', 'description', 'created_at']
    list_filter = ['entry_type']
    search_fields = ['merchant__name', 'description']


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ['merchant', 'key', 'response_status', 'created_at']
    search_fields = ['merchant__name', 'key']
