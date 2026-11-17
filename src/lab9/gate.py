"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
from math import inf, isfinite
from pathlib import Path
from statistics import mean

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item
from lab9.graders import GRADERS


def _report_rows(report: dict, spec: dict, name: str, problems: list[str]) -> dict:
    """Validate a report and index its rows by (item_id, seed)."""
    manifest = report.get("manifest", {})
    rows = report.get("rows")
    metrics = report.get("metrics")
    seeds = manifest.get("seeds")
    item_count = manifest.get("items")
    if (not isinstance(rows, list) or not isinstance(metrics, dict)
            or not isinstance(seeds, list) or not seeds
            or any(type(seed) is not int for seed in seeds)
            or type(item_count) is not int or item_count < 1):
        problems.append(f"{name}: invalid report manifest, rows or metrics")
        return {}

    if report.get("evaluator_failures"):
        problems.append(f"{name}: evaluator_failures is non-empty")
    for metric, value in metrics.items():
        if value is not None and (type(value) not in (int, float) or not isfinite(value)):
            problems.append(f"{name}: {metric} has a non-finite or invalid aggregate")

    graded = [metric["id"] for metric in spec["metrics"] if metric["id"] in GRADERS]
    indexed = {}
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get("item_id"), str)
                or type(row.get("seed")) is not int):
            problems.append(f"{name}: invalid row identity")
            continue
        pair = (row["item_id"], row["seed"])
        indexed[pair] = row
        tags = row.get("slices", [])
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            problems.append(f"{name}: {pair} has invalid slice tags")
        missing = [metric for metric in graded if type(row.get(metric)) is not bool]
        if missing:
            problems.append(f"{name}: {pair} has missing or invalid grader scores: {', '.join(missing)}")

    if len(indexed) != len(rows):
        problems.append(f"{name}: duplicate or invalid (item_id, seed) rows")
    if (len(seeds) != len(set(seeds)) or len(rows) != item_count * len(seeds)
            or len({item for item, _ in indexed}) != item_count
            or {seed for _, seed in indexed} != set(seeds)):
        problems.append(f"{name}: rows do not cover the manifest's item × seed grid")

    # Real harness reports carry a cost for every row. Recompute their aggregates
    # from the raw scores, including pass^k, to catch edited summary values.
    has_costs = "cost_per_success" in metrics or any(
        metric["id"] == "cost_per_success" for metric in spec["metrics"]
    )
    if has_costs:
        costs = [row.get("cost") for row in indexed.values()]
        if any(type(cost) not in (int, float) or not isfinite(cost) or cost < 0 for cost in costs):
            problems.append(f"{name}: invalid row costs")
        if not any(problem.startswith(f"{name}:") for problem in problems):
            expected = aggregate(rows, graded, k_values=spec.get("pass_k", []))
            for metric, value in expected.items():
                if metric not in metrics or metrics[metric] != value:
                    problems.append(f"{name}: {metric} aggregate disagrees with rows")
    return indexed


def _ratchet_problems(spec: dict, base_spec: dict) -> list[str]:
    """Report any weaker rule on the same eval-set version."""
    if spec.get("eval_set_version") != base_spec.get("eval_set_version"):
        return []
    problems = []
    for section, fields in (("metrics", ("id",)), ("slices", ("name", "metric"))):
        current = {tuple(rule[field] for field in fields): rule for rule in spec.get(section, [])}
        for old in base_spec.get(section, []):
            key = tuple(old[field] for field in fields)
            new = current.get(key)
            if new is None:
                problems.append(f"{section} {key}: rule removed")
                continue
            if old.get("blocking") and not new.get("blocking"):
                problems.append(f"{section} {key}: blocking disabled")
            before, after = old.get("threshold", old), new.get("threshold", new)
            for limit in ("min", "max", "max_increase"):
                if limit not in before:
                    continue
                value = after.get(limit)
                if (type(value) not in (int, float) or not isfinite(value)
                        or (value < before[limit] if limit == "min" else value > before[limit])):
                    problems.append(f"{section} {key}: loosened or removed {limit}")
            if before.get("no_significant_drop") and not after.get("no_significant_drop"):
                problems.append(f"{section} {key}: removed paired comparison")
    return problems


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """Reject unpaired data, broken graders, altered aggregates, and weaker rules."""
    problems: list[str] = []
    pr_rows = _report_rows(pr, spec, "PR", problems)
    base_rows = _report_rows(base, base_spec if base_spec is not None else spec, "baseline", problems)
    if pr_rows.keys() != base_rows.keys():
        problems.append("PR and baseline have different (item_id, seed) pairs")
    if not problems and any(
        sorted(row.get("slices", [])) != sorted(base_rows[pair].get("slices", []))
        for pair, row in pr_rows.items()
    ):
        problems.append("PR and baseline have different slice tags")
    if base_spec is not None:
        problems.extend(_ratchet_problems(spec, base_spec))
    return problems


def _paired_interval(pr_values: dict, base_values: dict, spec: dict) -> tuple[float, float, float]:
    keys = sorted(pr_values.keys() & base_values.keys())
    bootstrap = spec.get("bootstrap", {})
    return stats.paired_bootstrap(
        [pr_values[key] for key in keys], [base_values[key] for key in keys],
        n_resamples=bootstrap.get("n_resamples", 1000), rng=bootstrap.get("rng", 2027),
        confidence=bootstrap.get("confidence", 0.95),
    )


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """Apply floors and paired comparisons within each configured slice."""
    blocked, lines = [], []
    for rule in spec.get("slices", []):
        name, metric = rule["name"], rule["metric"]
        key = f"slice:{name}/{metric}"
        pr_values = per_item(pr, metric, name)
        base_values = per_item(base, metric, name)
        failed = not pr_values or pr_values.keys() != base_values.keys()
        note = "missing or unpaired items"
        if not failed:
            value = mean(pr_values.values())
            failed = value < rule.get("min", -inf) or value > rule.get("max", inf)
            note = f"{value:.4f}"
            if rule.get("no_significant_drop"):
                delta, lo, hi = _paired_interval(pr_values, base_values, spec)
                failed |= hi < 0
                note += f" Δ {delta:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
        blocking = failed and rule.get("blocking")
        if blocking:
            blocked.append(key)
        verdict = "BLOCK" if blocking else "warn" if failed else "ok"
        lines.append(f"  {key} {note} {verdict}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            d, lo, hi = _paired_interval(a, b, spec)
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
