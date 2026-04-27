import logging
import random
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import LedgerEntry, Payout

logger = logging.getLogger(__name__)

# 70% success, 20% failure, 10% hang (stays PROCESSING)
PAYOUT_OUTCOMES = ['success'] * 70 + ['failure'] * 20 + ['processing'] * 10


@shared_task(bind=True, max_retries=3)
def process_payout(self, payout_id: str):
    """
    Picks up a pending payout and simulates bank settlement.
      - success → COMPLETED (debit hold becomes the settlement)
      - failure → FAILED, funds returned via CREDIT entry (atomic with status change)
      - processing → stays PROCESSING; check_stuck_payouts retries it
    """
    try:
        with transaction.atomic():
            payout = Payout.objects.select_for_update().get(id=payout_id)
            if payout.status != 'PENDING':
                logger.info(
                    "Payout %s already in %s, skipping.", payout_id, payout.status
                )
                return
            payout.transition_to('PROCESSING')
            payout.attempts += 1
            payout.last_attempted_at = timezone.now()
            payout.save()
    except Payout.DoesNotExist:
        logger.error("Payout %s not found", payout_id)
        return

    # Simulate bank call OUTSIDE the transaction (don't hold DB locks during I/O).
    outcome = random.choice(PAYOUT_OUTCOMES)
    logger.info("Payout %s outcome: %s", payout_id, outcome)

    if outcome == 'processing':
        # Hangs intentionally — check_stuck_payouts handles recovery.
        return

    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(id=payout_id)
        if payout.status != 'PROCESSING':
            return

        if outcome == 'success':
            payout.transition_to('COMPLETED')
            payout.save()
            logger.info("Payout %s COMPLETED", payout_id)
        elif outcome == 'failure':
            payout.transition_to('FAILED')
            payout.save()
            # Fund return atomic with state transition.
            LedgerEntry.objects.create(
                merchant=payout.merchant,
                amount=payout.amount_paise,
                entry_type='CREDIT',
                description=f'Payout failed — refund — {payout.id}',
                payout=payout,
            )
            logger.info("Payout %s FAILED — funds returned", payout_id)


@shared_task
def check_stuck_payouts():
    """
    Finds payouts stuck in PROCESSING for >30 seconds.
    Retries up to 3 attempts with exponential backoff.
    On final failure, transitions to FAILED and returns funds atomically.
    """
    cutoff = timezone.now() - timedelta(seconds=30)
    stuck = Payout.objects.filter(status='PROCESSING', last_attempted_at__lt=cutoff)

    for payout in stuck:
        if payout.attempts < 3:
            countdown = 2 ** payout.attempts
            with transaction.atomic():
                p = Payout.objects.select_for_update().get(id=payout.id)
                if p.status != 'PROCESSING':
                    continue
                # Internal retry — direct status reset is the only legitimate
                # bypass of the state machine, gated to this beat task.
                p.status = 'PENDING'
                p.save(update_fields=['status', 'updated_at'])
            process_payout.apply_async(args=[str(payout.id)], countdown=countdown)
            logger.info(
                "Retrying stuck payout %s (attempt %s, in %ss)",
                payout.id, payout.attempts, countdown,
            )
        else:
            with transaction.atomic():
                p = Payout.objects.select_for_update().get(id=payout.id)
                if p.status != 'PROCESSING':
                    continue
                p.transition_to('FAILED')
                p.save()
                LedgerEntry.objects.create(
                    merchant=p.merchant,
                    amount=p.amount_paise,
                    entry_type='CREDIT',
                    description=f'Payout max retries exceeded — refund — {p.id}',
                    payout=p,
                )
            logger.info("Payout %s exceeded retries — FAILED + funds returned", p.id)
