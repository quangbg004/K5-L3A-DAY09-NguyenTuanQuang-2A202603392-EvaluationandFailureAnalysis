"""Shape B — one ReAct agent. Student work.

Use `lab8.runtime.run_react` with max_steps=8. `decide` may pick a read tool.
It must not call `issue_refund`. After the loop, the host validates the quote
and is the only writer.

A decide() that trusts ticket text over the order row will fail hidden claims
where the customer overstates the delay or cites a superseded clause.

Per-order cap: an order may already have been refunded by an earlier claim.
The read tool `lookup_refund_history` shows how much. The host still enforces
the cap, so pass the full quote to `durability.issue_refund`, not a net amount.

Caps: stop at 8 steps. Count model calls in the Budget so cost stays comparable.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

import sqlite3

from lab8.db import connect
from lab8.durability import issue_refund
from lab8.runtime import run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.tools import get_claim_view, tool_cost
from lab8.trace import Trace
from lab8.mock_llm import complete


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


def _run(conn: sqlite3.Connection, claim_id: str, *, seed: int, crash_at: str | None) -> RunResult:
    budget = Budget()
    run_id = make_run_id("single", claim_id, seed)
    trace = Trace(run_id)

    def result(status: str, proposal: int = 0, reason: str | None = None) -> RunResult:
        trace.add("decision", {"status": status, "proposal_amount": proposal, "reason": reason})
        return finish(
            conn, shape="single", claim_id=claim_id, seed=seed,
            status=status, proposal_amount=proposal, budget=budget,
            trace=trace, error_reason=reason,
        )

    budget.add_tool(tool_cost())
    claim = get_claim_view(conn, claim_id)
    trace.add("claim_lookup", {"found": claim["found"]})
    if not claim["found"]:
        return result("failed", reason="unknown_claim")
    if not claim["order_id"]:
        return result("needs_info", reason="missing_order_id")

    def decide(observation: dict) -> dict:
        last_tool = observation.get("last_tool")
        # MockLLM emits text, not structured tool calls. This bounded adapter
        # maps observations to read actions; money and permissions stay in code.
        complete(budget, seed=seed, purpose="react", prompt=f"last_tool={last_tool}")
        if last_tool is None:
            trace.add("react_action", {"tool": "lookup_order"})
            return {"tool": "lookup_order", "args": {
                "order_id": claim["order_id"], "principal_id": claim["principal_id"],
            }}
        observed = observation["last_result"]
        if last_tool == "lookup_order":
            trace.add("order_lookup", {"visible": observed["visible"], "reason": observed["reason"]})
            if not observed["visible"]:
                return {"final": {"status": "escalated", "reason": observed["reason"]}}
            trace.add("react_action", {"tool": "compute_compensation"})
            return {"tool": "compute_compensation", "args": {"order": observed["order"]}}
        if last_tool == "compute_compensation":
            trace.add("quote", observed)
            return {"final": {"status": "quoted", "quote": observed}}
        return {"final": {"status": "failed", "reason": "unexpected_observation"}}

    loop = run_react(
        conn, budget, observation={}, decide=decide, max_steps=8, worker=True,
    )
    if loop["stopped"] != "final":
        return result("failed", reason="step_cap")
    final = loop["final"]
    if final["status"] != "quoted":
        return result(final["status"], reason=final.get("reason"))
    quote = final["quote"]
    proposal = int(quote["amount_vnd"])
    if proposal <= 0:
        return result("denied", reason=quote["reason"])

    # Refund is outside the read-only ReAct loop and uses the full quote.
    budget.add_tool(tool_cost())
    trace.add("refund_request", {"proposal_amount": proposal})
    trace.write()
    outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    trace.add("refund_outcome", {"ok": outcome["ok"], "reason": outcome["reason"]})
    if not outcome["ok"]:
        return result("failed" if outcome["conflict"] else "denied", proposal, outcome["reason"])
    return result("resolved", proposal)
