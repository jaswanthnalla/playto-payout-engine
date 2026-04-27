import uuid
from threading import Thread

from django.db import connections
from django.db.models import Q, Sum
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from payouts.models import IdempotencyKey, LedgerEntry, Merchant, Payout


def _make_merchant(balance_paise=10000):
    merchant = Merchant.objects.create(
        name='Test Merchant',
        email=f'test_{uuid.uuid4()}@test.com',
        bank_accounts=[{'id': 'acc_test', 'bank': 'HDFC', 'account': '****0000'}],
    )
    LedgerEntry.objects.create(
        merchant=merchant,
        amount=balance_paise,
        entry_type='CREDIT',
        description='Test seed credit',
    )
    return merchant


class ConcurrencyTest(TransactionTestCase):
    """
    Two simultaneous 6000-paise requests against a 10000-paise balance.
    Exactly one must succeed; the other must be rejected.
    """

    def test_concurrent_overdraw_prevention(self):
        merchant = _make_merchant(balance_paise=10000)
        results = []

        def make_request(idem_key):
            client = APIClient()
            response = client.post(
                '/api/v1/payouts',
                data={
                    'merchant_id': str(merchant.id),
                    'amount_paise': 6000,
                    'bank_account_id': 'acc_test',
                },
                headers={'Idempotency-Key': idem_key},
                format='json',
            )
            results.append(response.status_code)
            connections.close_all()

        t1 = Thread(target=make_request, args=[str(uuid.uuid4())])
        t2 = Thread(target=make_request, args=[str(uuid.uuid4())])
        t1.start(); t2.start()
        t1.join(); t2.join()

        success = results.count(201)
        rejected = results.count(402)

        self.assertEqual(success, 1, f"Exactly one should succeed; got {results}")
        self.assertEqual(rejected, 1, f"Exactly one should be rejected; got {results}")

        agg = LedgerEntry.objects.filter(merchant=merchant).aggregate(
            credits=Sum('amount', filter=Q(entry_type='CREDIT')),
            debits=Sum('amount', filter=Q(entry_type='DEBIT')),
        )
        net = (agg['credits'] or 0) - (agg['debits'] or 0)
        self.assertGreaterEqual(net, 0, "Balance must never go negative")


class IdempotencyTest(TransactionTestCase):
    def test_idempotent_payout_request(self):
        merchant = _make_merchant(balance_paise=10000)
        client = APIClient()
        idem_key = str(uuid.uuid4())
        body = {
            'merchant_id': str(merchant.id),
            'amount_paise': 5000,
            'bank_account_id': 'acc_test',
        }
        headers = {'Idempotency-Key': idem_key}

        r1 = client.post('/api/v1/payouts', data=body, headers=headers, format='json')
        r2 = client.post('/api/v1/payouts', data=body, headers=headers, format='json')

        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(r1.data['id'], r2.data['id'])
        self.assertEqual(Payout.objects.filter(merchant=merchant).count(), 1)

    def test_missing_idempotency_key_rejected(self):
        merchant = _make_merchant()
        client = APIClient()
        r = client.post(
            '/api/v1/payouts',
            data={
                'merchant_id': str(merchant.id),
                'amount_paise': 1000,
                'bank_account_id': 'acc_test',
            },
            format='json',
        )
        self.assertEqual(r.status_code, 400)


class StateMachineTest(TransactionTestCase):
    def _make_payout(self, status):
        merchant = _make_merchant()
        return Payout.objects.create(
            merchant=merchant,
            amount_paise=1000,
            bank_account_id='acc_test',
            idempotency_key=str(uuid.uuid4()),
            status=status,
        )

    def test_completed_to_pending_blocked(self):
        p = self._make_payout('COMPLETED')
        with self.assertRaises(ValueError):
            p.transition_to('PENDING')

    def test_failed_to_completed_blocked(self):
        p = self._make_payout('FAILED')
        with self.assertRaises(ValueError):
            p.transition_to('COMPLETED')

    def test_pending_to_processing_allowed(self):
        p = self._make_payout('PENDING')
        p.transition_to('PROCESSING')
        self.assertEqual(p.status, 'PROCESSING')

    def test_pending_to_completed_blocked(self):
        p = self._make_payout('PENDING')
        with self.assertRaises(ValueError):
            p.transition_to('COMPLETED')


class InsufficientBalanceTest(TransactionTestCase):
    def test_rejects_when_under_balance(self):
        merchant = _make_merchant(balance_paise=1000)
        client = APIClient()
        r = client.post(
            '/api/v1/payouts',
            data={
                'merchant_id': str(merchant.id),
                'amount_paise': 5000,
                'bank_account_id': 'acc_test',
            },
            headers={'Idempotency-Key': str(uuid.uuid4())},
            format='json',
        )
        self.assertEqual(r.status_code, 402)
        self.assertEqual(Payout.objects.filter(merchant=merchant).count(), 0)
