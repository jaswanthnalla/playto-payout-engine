import logging

from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import IdempotencyKey, LedgerEntry, Merchant, Payout
from .serializers import (
    MerchantDashboardSerializer,
    MerchantSerializer,
    PayoutSerializer,
)
from .tasks import process_payout

logger = logging.getLogger(__name__)


class PayoutRequestView(APIView):
    """
    POST /api/v1/payouts
    Header: Idempotency-Key: <uuid>
    Body: { "merchant_id": "...", "amount_paise": 10000, "bank_account_id": "acc_xxx" }
    """

    def post(self, request):
        idempotency_key = request.headers.get('Idempotency-Key')
        if not idempotency_key:
            return Response(
                {'error': 'Idempotency-Key header required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        merchant_id = request.data.get('merchant_id')
        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except (Merchant.DoesNotExist, ValueError):
            return Response({'error': 'Merchant not found'}, status=404)

        # Idempotency replay check (before any DB writes).
        try:
            existing_key = IdempotencyKey.objects.get(
                merchant=merchant, key=idempotency_key
            )
            if not existing_key.is_expired():
                return Response(
                    existing_key.response_body,
                    status=existing_key.response_status,
                )
            existing_key.delete()
        except IdempotencyKey.DoesNotExist:
            pass

        amount_paise = request.data.get('amount_paise')
        bank_account_id = request.data.get('bank_account_id')

        if not isinstance(amount_paise, int) or amount_paise <= 0:
            return Response(
                {'error': 'amount_paise must be a positive integer'}, status=400
            )
        if not bank_account_id:
            return Response({'error': 'bank_account_id required'}, status=400)

        # Concurrency-safe balance check + fund hold.
        try:
            with transaction.atomic():
                merchant_locked = Merchant.objects.select_for_update().get(
                    id=merchant.id
                )

                agg = LedgerEntry.objects.filter(
                    merchant=merchant_locked
                ).aggregate(
                    credits=Sum('amount', filter=Q(entry_type='CREDIT')),
                    debits=Sum('amount', filter=Q(entry_type='DEBIT')),
                )
                available = (agg['credits'] or 0) - (agg['debits'] or 0)

                if available < amount_paise:
                    response_body = {
                        'error': 'Insufficient balance',
                        'available_paise': available,
                        'requested_paise': amount_paise,
                    }
                    IdempotencyKey.objects.create(
                        merchant=merchant_locked,
                        key=idempotency_key,
                        response_body=response_body,
                        response_status=402,
                    )
                    return Response(response_body, status=402)

                payout = Payout.objects.create(
                    merchant=merchant_locked,
                    amount_paise=amount_paise,
                    bank_account_id=bank_account_id,
                    idempotency_key=idempotency_key,
                    status='PENDING',
                )

                LedgerEntry.objects.create(
                    merchant=merchant_locked,
                    amount=amount_paise,
                    entry_type='DEBIT',
                    description=f'Payout hold — {payout.id}',
                    payout=payout,
                )

                response_body = PayoutSerializer(payout).data
                response_status_code = status.HTTP_201_CREATED

                IdempotencyKey.objects.create(
                    merchant=merchant_locked,
                    key=idempotency_key,
                    response_body=response_body,
                    response_status=response_status_code,
                )

        except IntegrityError:
            # Lost race: a concurrent request committed first with the same idempotency key.
            existing = IdempotencyKey.objects.filter(
                merchant=merchant, key=idempotency_key
            ).first()
            if existing and not existing.is_expired():
                return Response(
                    existing.response_body, status=existing.response_status
                )
            return Response({'error': 'Conflict on idempotency key'}, status=409)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Payout request failed")
            return Response({'error': str(exc)}, status=500)

        # Dispatch to Celery AFTER commit.
        try:
            process_payout.delay(str(payout.id))
        except Exception:  # noqa: BLE001
            logger.exception("Failed to enqueue process_payout — beat will recover")

        return Response(response_body, status=response_status_code)


class MerchantListView(APIView):
    def get(self, request):
        merchants = Merchant.objects.all().order_by('name')
        return Response(MerchantSerializer(merchants, many=True).data)


class MerchantDashboardView(APIView):
    def get(self, request, merchant_id):
        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        return Response(MerchantDashboardSerializer(merchant).data)


class PayoutListView(APIView):
    def get(self, request, merchant_id):
        payouts = Payout.objects.filter(merchant_id=merchant_id).order_by(
            '-created_at'
        )
        return Response(PayoutSerializer(payouts, many=True).data)


class PayoutDetailView(APIView):
    def get(self, request, payout_id):
        try:
            payout = Payout.objects.get(id=payout_id)
        except Payout.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        return Response(PayoutSerializer(payout).data)
