"""Shape C — delegate order lookup and keep refund decisions in the host."""

from __future__ import annotations

import sqlite3
from contextlib import closing

from lab8.db import connect
from lab8.durability import issue_refund
from lab8.handoff import make_handoff
from lab8.runtime import run_readonly_investigators
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.tools import compute_compensation, get_claim_view, tool_cost
from lab8.trace import Trace


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    with closing(connect(store_path)) as conn:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)


def _run(conn: sqlite3.Connection, claim_id: str, *, seed: int, crash_at: str | None) -> RunResult:
    budget = Budget()
    trace = Trace(make_run_id("orchestrator", claim_id, seed))

    def finish_claim(status: str, proposal: int = 0, reason: str | None = None) -> RunResult:
        trace.add("decision", {"status": status})
        return finish(
            conn,
            shape="orchestrator",
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=reason,
        )

    budget.add_tool(tool_cost())
    claim = get_claim_view(conn, claim_id)
    if not claim["found"]:
        return finish_claim("failed", reason="unknown_claim")
    if not claim["order_id"]:
        return finish_claim("needs_info", reason="missing_order_id")

    handoff = make_handoff(
        request_id=f"REQ-{trace.run_id}",
        claim_id=claim_id,
        task="lookup_claim_order",
        facts={},
        allowed_tools=["lookup_order"],
    )
    trace.add("handoff", handoff)
    investigation = run_readonly_investigators(conn, budget, handoff, principal_id=claim["principal_id"])
    order_view = investigation["tools"]["lookup_order"]
    trace.add("investigator", {"tool": "lookup_order", "visible": order_view["visible"]})
    if not order_view["visible"]:
        return finish_claim("escalated", reason=order_view["reason"])

    budget.add_tool(tool_cost())
    quote = compute_compensation(conn, order_view["order"])
    proposal = quote["amount_vnd"]
    trace.add("quote", {"amount_vnd": proposal})
    if proposal <= 0:
        return finish_claim("denied", reason=quote["reason"])

    # Give the host the full quote so it can apply the per-order cap atomically.
    budget.add_tool(tool_cost())
    trace.add("refund_attempt", {"proposal_amount": proposal})
    if crash_at is not None:
        # Persist the safe trace before the host can interrupt the run.
        trace.write()
    outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    if outcome["ok"]:
        return finish_claim("resolved", proposal)
    status = "failed" if outcome["conflict"] else "denied"
    return finish_claim(status, proposal, outcome["reason"])
