"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []
    for metric_id, value in (pr.get("metrics") or {}).items():
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            problems.append(f"metric {metric_id} is NaN or inf")

    pr_manifest = pr.get("manifest") or {}
    base_manifest = base.get("manifest") or {}
    pr_items = pr_manifest.get("items")
    pr_seeds = pr_manifest.get("seeds") or []
    pr_rows = pr.get("rows") or []
    if pr_items is not None and len(pr_rows) != int(pr_items) * len(pr_seeds):
        problems.append("row count differs from manifest items x seeds")

    pr_pairs = {(r.get("item_id"), r.get("seed")) for r in pr_rows}
    base_pairs = {(r.get("item_id"), r.get("seed")) for r in (base.get("rows") or [])}
    if pr_pairs != base_pairs:
        problems.append("PR item/seed set differs from baseline")

    if pr.get("evaluator_failures"):
        problems.append("evaluator_failures is not empty")

    graded_ids = {m["id"] for m in spec.get("metrics", [])
                  if m["id"] in {k for k in (pr_manifest and pr_rows[0])} if pr_rows}
    for row in pr_rows:
        for metric_id in graded_ids:
            if row.get(metric_id) is None:
                problems.append(f"{row.get('item_id')}@{row.get('seed')} has None for {metric_id}")

    if base_spec is not None:
        if spec.get("eval_set_version") == base_spec.get("eval_set_version"):
            base_metrics = {m["id"]: m for m in base_spec.get("metrics", [])}
            pr_metrics = {m["id"]: m for m in spec.get("metrics", [])}
            if set(pr_metrics) != set(base_metrics):
                problems.append("metric set differs from baseline spec")
            for metric_id, base_metric in base_metrics.items():
                pr_metric = pr_metrics.get(metric_id)
                if pr_metric is None:
                    continue
                base_th = base_metric.get("threshold") or {}
                pr_th = pr_metric.get("threshold") or {}
                if "max" in base_th and ("max" not in pr_th or pr_th["max"] > base_th["max"]):
                    problems.append(f"{metric_id}: max threshold loosened")
                if "min" in base_th and ("min" not in pr_th or pr_th["min"] < base_th["min"]):
                    problems.append(f"{metric_id}: min threshold loosened")
                if base_th.get("no_significant_drop") and not pr_th.get("no_significant_drop"):
                    problems.append(f"{metric_id}: no_significant_drop removed")
                if base_metric.get("blocking") and not pr_metric.get("blocking"):
                    problems.append(f"{metric_id}: blocking changed")

            base_slices = {s["name"]: s for s in base_spec.get("slices") or []}
            pr_slices = {s["name"]: s for s in spec.get("slices") or []}
            if set(pr_slices) != set(base_slices):
                problems.append("slice set differs from baseline spec")
            for name, base_slice in base_slices.items():
                pr_slice = pr_slices.get(name)
                if pr_slice is None:
                    continue
                if "min" in base_slice and ("min" not in pr_slice or pr_slice["min"] < base_slice["min"]):
                    problems.append(f"slice {name}: min threshold loosened")
                if base_slice.get("no_significant_drop") and not pr_slice.get("no_significant_drop"):
                    problems.append(f"slice {name}: no_significant_drop removed")
                if base_slice.get("blocking") and not pr_slice.get("blocking"):
                    problems.append(f"slice {name}: blocking changed")

    pr_slice_tags = {
        r.get("item_id"): tuple(sorted(r.get("slices") or []))
        for r in pr_rows
    }
    base_slice_tags = {
        r.get("item_id"): tuple(sorted(r.get("slices") or []))
        for r in (base.get("rows") or [])
    }
    if pr_slice_tags != base_slice_tags:
        problems.append("item slice tags differ from baseline")
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})
    for sl in spec.get("slices") or []:
        name = sl["name"]
        metric = sl["metric"]
        pr_item = per_item(pr, metric, slice_name=name)
        base_item = per_item(base, metric, slice_name=name)
        values = list(pr_item.values())
        value = sum(values) / len(values) if values else None
        verdict = "ok"
        note = ""
        if value is None:
            verdict = "missing"
        elif "min" in sl and value < sl["min"]:
            verdict = "fail"
        if sl.get("no_significant_drop") and pr_item and base_item:
            keys = sorted(set(pr_item) & set(base_item))
            d, lo, hi = stats.paired_bootstrap(
                [pr_item[k] for k in keys],
                [base_item[k] for k in keys],
                n_resamples=bs.get("n_resamples", 1000),
                rng=bs.get("rng", 2027),
            )
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        metric_id = f"slice:{name}/{metric}"
        if verdict != "ok" and sl.get("blocking"):
            blocked.append(metric_id)
        label = "ok" if verdict == "ok" else ("MISSING" if verdict == "missing" else
                                             ("BLOCK" if sl.get("blocking") else "warn"))
        lines.append(f"  {metric_id:<22} {value!s:<8} {json.dumps(sl):<40} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
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
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
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
