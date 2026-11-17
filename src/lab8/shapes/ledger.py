"""CP3 ledger integration. CP2 owns investigation and computing the full quote."""

from __future__ import annotations

import sqlite3

from lab8 import durability
from lab8.schemas import Budget, RunResult
from lab8.shapes.common import finish
from lab8.trace import Trace


def finish_refund(
    conn: sqlite3.Connection,
    *,
    shape: str,
    claim_id: str,
    seed: int,
    proposal_amount: int,
    budget: Budget,
    trace: Trace,
    crash_at: str | None = None,
) -> RunResult:
    """Host-only final step for a positive, full entitlement quote.

    Do not subtract prior refunds: durability handles the order cap. A replay
    uses refund:{claim_id}. InjectedCrash deliberately propagates to the caller;
    the shape should close its connection in finally, without swallowing it.
    CP2 handles zero quotes and other early returns before calling this helper.
    """
    outcome = durability.issue_refund(
        conn, claim_id, proposal_amount, crash_at=crash_at
    )
    status = "resolved" if outcome["ok"] else (
        "failed" if outcome["conflict"] else "denied"
    )
    trace.add("decision", {"status": status, "reason": outcome["reason"]})
    return finish(
        conn,
        shape=shape,
        claim_id=claim_id,
        seed=seed,
        status=status,
        proposal_amount=proposal_amount,
        budget=budget,
        trace=trace,
        error_reason=None if outcome["ok"] else outcome["reason"],
    )
