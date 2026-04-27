"""
Documentation of the Payout state machine. Enforcement lives on the model
(`Payout.transition_to`). This file exists to make the rules grep-able and
to centralise the legal-transitions table for any future readers.

States:
    PENDING     — payout created, funds held via DEBIT ledger entry
    PROCESSING  — Celery worker has picked it up and called the bank
    COMPLETED   — bank confirmed settlement; debit hold becomes the settlement
    FAILED      — bank rejected or retries exhausted; CREDIT refund posted

Legal transitions:
    PENDING    → PROCESSING
    PROCESSING → COMPLETED | FAILED
    COMPLETED  → (terminal)
    FAILED     → (terminal)

Any other transition raises ValueError. The Celery worker MUST go through
`transition_to`. The only exception is the stuck-payout retry path, which
resets PROCESSING → PENDING for re-dispatch — see tasks.check_stuck_payouts.
"""

LEGAL_TRANSITIONS = {
    'PENDING': ['PROCESSING'],
    'PROCESSING': ['COMPLETED', 'FAILED'],
    'COMPLETED': [],
    'FAILED': [],
}
