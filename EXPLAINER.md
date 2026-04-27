# EXPLAINER.md — Playto Payout Engine

This document explains the five things the CTO is grading: the ledger, the lock, idempotency, the state machine, and the AI audit. Every claim below maps to specific code.

---

## 1. The Ledger

**Where balance comes from:**

```python
# backend/payouts/models.py — Merchant.get_balance
agg = LedgerEntry.objects.filter(merchant=self).aggregate(
    credits=Sum('amount', filter=Q(entry_type='CREDIT')),
    debits=Sum('amount', filter=Q(entry_type='DEBIT')),
)
available = (agg['credits'] or 0) - (agg['debits'] or 0)

held = LedgerEntry.objects.filter(
    merchant=self,
    entry_type='DEBIT',
    payout__status__in=['PENDING', 'PROCESSING'],
).aggregate(total=Sum('amount'))['total'] or 0
```

**Why this model.** Balance is *never* a stored column. It's always derived from the ledger via a single aggregate query. This makes balance impossible to drift from reality — there is no `merchant.current_balance` field that could ever disagree with the ledger because no such field exists.

**Append-only, integers, paise.** `LedgerEntry.amount` is a `BigIntegerField` and is always positive (the sign is encoded in `entry_type ∈ {CREDIT, DEBIT}`). Every monetary field on every model is `BigIntegerField` in paise — there is no `FloatField` and no `DecimalField`. Floats lose precision; decimals are fine but unnecessary if you commit to integer paise. Entries are never edited or deleted: a failed payout is corrected by appending a new `CREDIT` entry, not by mutating the original `DEBIT`.

**Hold semantics.** When a payout is requested, we immediately write a `DEBIT` entry tied to that payout. That entry stays in the ledger forever. If the payout completes, the debit becomes the settlement (no further entry needed). If the payout fails, we append a compensating `CREDIT` (atomically — see §4). `held_balance` is just the sum of `DEBIT` entries whose payout is still `PENDING` or `PROCESSING`.

---

## 2. The Lock

**Exact code:**

```python
# backend/payouts/views.py — PayoutRequestView.post
with transaction.atomic():
    merchant_locked = Merchant.objects.select_for_update().get(id=merchant.id)

    agg = LedgerEntry.objects.filter(merchant=merchant_locked).aggregate(
        credits=Sum('amount', filter=Q(entry_type='CREDIT')),
        debits=Sum('amount', filter=Q(entry_type='DEBIT')),
    )
    available = (agg['credits'] or 0) - (agg['debits'] or 0)

    if available < amount_paise:
        # ... reject ...

    payout = Payout.objects.create(...)
    LedgerEntry.objects.create(entry_type='DEBIT', payout=payout, ...)
```

**How it works.** `select_for_update()` translates to `SELECT ... FOR UPDATE` in PostgreSQL, taking a row-level lock on the merchant row. Any second transaction calling `select_for_update()` on the same row blocks at the SELECT until the first transaction commits or rolls back.

**Why it prevents overdraw.** Imagine merchant has ₹100 and two simultaneous ₹60 requests arrive:

1. Request A enters its `transaction.atomic()`, locks the merchant row, reads available = 10000 paise, sees 10000 ≥ 6000, creates the Payout + DEBIT, **commits**.
2. Request B enters its block at roughly the same moment, calls `select_for_update()` on the same merchant — and *blocks* at the SELECT. It waits.
3. When A commits, B unblocks, **re-reads** the aggregate (now 10000 - 6000 = 4000), sees 4000 < 6000, rejects with HTTP 402.

Without the lock, both requests would read 10000, both create DEBITs, and the merchant ends up at -2000 paise. The aggregate is computed *inside* the locked transaction, so it reflects every committed write up to that moment — there is no chance of a race between "read balance" and "write debit."

**Why row-level (database) and not Python.** A `threading.Lock` works only inside one Python process. We have multiple Gunicorn workers and multiple Celery workers — they don't share Python locks. PostgreSQL's row lock is the only primitive that all of them respect.

**This is tested.** `payouts/tests.py::ConcurrencyTest::test_concurrent_overdraw_prevention` fires two real threads at the API. The assertion is `success == 1, rejected == 1` — and it passes because the lock works.

---

## 3. The Idempotency

**The model:**

```python
# backend/payouts/models.py
class IdempotencyKey(models.Model):
    merchant = models.ForeignKey(Merchant, ...)
    key = models.CharField(max_length=255)
    response_body = models.JSONField()
    response_status = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('merchant', 'key')]
```

Plus `Payout` has `unique_together = [('merchant', 'idempotency_key')]` — a second hard constraint at the DB level.

**Replay path.** First thing the view does, before any writes:

```python
existing_key = IdempotencyKey.objects.get(merchant=merchant, key=idempotency_key)
if not existing_key.is_expired():
    return Response(existing_key.response_body, status=existing_key.response_status)
```

A replay returns the *exact same* response body and status as the first call. The cached payload includes the original `payout.id`, so the client can keep polling for that ID.

**Mid-flight collision.** What happens if request 2 arrives while request 1 is still inside `transaction.atomic()`?

1. R2 does `IdempotencyKey.objects.get(...)` — sees nothing, because R1 hasn't committed yet (read-committed isolation hides R1's uncommitted insert).
2. R2 falls through to the atomic block and calls `select_for_update()` on the merchant — and **blocks** there, because R1 holds the lock.
3. R1 commits. Both the `Payout` row and the `IdempotencyKey` row are now visible.
4. R2 unblocks and reaches `Payout.objects.create(idempotency_key=...)`. The DB rejects with `IntegrityError` due to `unique_together`.
5. We catch `IntegrityError` and re-read the `IdempotencyKey`, returning the cached response. Client sees the same response as R1 — exactly as it should.

**Rejections cached too.** A 402 "insufficient balance" response is also cached against the idempotency key. Replaying the same key will return 402 again, not silently retry on a now-funded account. Idempotency means "same result for same key," not "retry until success."

**Expiry.** Keys expire after 24 hours. Past that, the key is deleted on read and the request is treated as fresh.

---

## 4. The State Machine

**The table:**

```python
# backend/payouts/models.py
LEGAL_TRANSITIONS = {
    'PENDING': ['PROCESSING'],
    'PROCESSING': ['COMPLETED', 'FAILED'],
    'COMPLETED': [],   # terminal
    'FAILED': [],      # terminal
}

def transition_to(self, new_status):
    legal = self.LEGAL_TRANSITIONS.get(self.status, [])
    if new_status not in legal:
        raise ValueError(f"Illegal transition: {self.status} → {new_status}. Legal: {legal}")
    self.status = new_status
```

**Where it's used.** Every status mutation in `tasks.py` goes through `transition_to`. There is one — and only one — place in the code that ever writes `payout.status = ...` directly: the stuck-payout retry path in `check_stuck_payouts`, which resets `PROCESSING → PENDING` so the worker can pick it up again. That's documented in `state_machine.py` and is the only legitimate state-machine bypass.

**Why FAILED → COMPLETED is impossible.** `FAILED` maps to an empty list. `transition_to('COMPLETED')` from FAILED checks `'COMPLETED' in []` and raises `ValueError`. There is no view or task path that bypasses this — `transition_to` is the only entry point.

**Atomicity of fund return.** When a payout transitions to `FAILED`, the compensating `CREDIT` ledger entry is written in the *same* `transaction.atomic()` block:

```python
# backend/payouts/tasks.py
with transaction.atomic():
    payout = Payout.objects.select_for_update().get(id=payout_id)
    if payout.status != 'PROCESSING':
        return
    payout.transition_to('FAILED')
    payout.save()
    LedgerEntry.objects.create(
        merchant=payout.merchant,
        amount=payout.amount_paise,
        entry_type='CREDIT',
        description=f'Payout failed — refund — {payout.id}',
        payout=payout,
    )
```

If the CREDIT insert fails, the FAILED status change rolls back too — they commit as one. There is no window where status=FAILED but funds are not yet returned.

**Idempotent worker.** `process_payout` always re-reads with `select_for_update()` and checks `payout.status` before acting. If the payout is already in a terminal state (e.g. because beat redispatched it and another worker already processed it), the task returns early. Celery at-least-once delivery is safe here.

**Stuck-payout recovery.** A payout can get stuck in `PROCESSING` (the simulator emits this 10% of the time to model real-world bank timeouts). `check_stuck_payouts` runs every 60s via Celery beat, finds payouts in `PROCESSING` for >30s, and either re-dispatches them with exponential backoff (attempts < 3) or transitions them to `FAILED` and refunds (attempts ≥ 3) — always atomically.

---

## 5. The AI Audit

**What an LLM suggested (wrong):**

```python
# AI-generated balance check
merchant = Merchant.objects.get(id=merchant_id)
if merchant.current_balance >= amount_paise:
    merchant.current_balance -= amount_paise
    merchant.save()
    Payout.objects.create(...)
```

**Three things wrong with this:**

1. **No row lock.** Two concurrent transactions both read `current_balance = 10000`, both subtract 6000, both write 4000. The merchant has been overdrawn by 2000 paise and neither transaction sees a conflict.
2. **Stored balance.** `current_balance` is a column. It can — and over time *will* — drift from the actual ledger. Any bug that creates a debit without decrementing the column (or vice versa) is a permanent corruption that's invisible until an auditor compares aggregates.
3. **Python-side arithmetic.** `merchant.current_balance -= amount_paise` happens in Python, then is written back. Even with a lock, this is fragile — if anything between the read and the write throws, the in-memory state and DB state diverge. DB-side aggregates inside the locked transaction don't have this problem because they read committed state directly.

**What I replaced it with.**

- `select_for_update()` on the merchant row inside `transaction.atomic()` — serialises concurrent requests at the database, not in Python.
- Balance derived from `LedgerEntry.objects.aggregate(...)` on every request. There is no balance column to drift.
- The DEBIT entry and the Payout row are created in the same atomic block, so they commit together or not at all.
- Compensating CREDIT on failure happens in the same atomic block as the `transition_to('FAILED')` — fund return is never separable from the status change.

The result: the invariant `sum(CREDITs) - sum(DEBITs) ≥ 0` is enforced at the database level on every successful request, the ledger is the single source of truth, and the state machine prevents anyone — including future-me — from corrupting it.
