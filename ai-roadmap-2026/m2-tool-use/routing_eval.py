"""
routing_eval.py — Month 2, Week 2

Measure how well the model picks tools, and how much of that is down to the
descriptions.

THREE METRICS, BECAUSE THEY HAVE THREE DIFFERENT FIXES
------------------------------------------------------
  selection accuracy   did it call the right tool(s)?
                       wrong -> the DESCRIPTIONS misled it

  argument accuracy    right tool, right arguments?
                       wrong -> the SCHEMA field descriptions are unclear
                       (Week 1 hit this: a required `query` forced the model to
                       invent "job", which matched nothing)

  over-retrieval       did it call a tool when none was needed?
                       the category most eval sets omit, and the only one that
                       catches an agent doing expensive work for nothing

A single "accuracy" number hides which of these you have, and they are not
fixed the same way.

TRAJECTORY MATCHING IS SET-BASED
--------------------------------
Compared as sets, not exact sequences. If a question needs search_jobs and
get_job_details, the order is usually forced by data dependency anyway, and
demanding an exact sequence manufactures failures that are not real.

Run:  python routing_eval.py                 both variants
      python routing_eval.py overlapping     just one
"""

import json
import sys
from collections import Counter

import descriptions
import tools  # noqa: F401 — registers them
from agent import IterationCapExceeded, run
from guardrails import Budget, Session

EVAL_SET = "eval_sets/routing.json"


def score_case(case: dict, trace: list[dict]) -> dict:
    """Compare what the agent did against what the case expected."""
    # Map neutralised names (tool_a) back to real ones, so the neutral-name
    # variants are scored against the same expectations as the others.
    called = [descriptions.real_name(t["tool"]) for t in trace if t["tool"]]
    expected = case["expected_tools"]

    # Set-based: did it use the right tools, regardless of order or repeats?
    got_set, want_set = set(called), set(expected)
    selection_ok = got_set == want_set

    # Over-retrieval: expected no tools, used some.
    over_retrieved = not expected and bool(called)

    # Argument accuracy only means something if the right tool was called.
    # Checks the fields the case specified; ignores the rest.
    arg_ok = None
    if case["expected_args"] and selection_ok:
        arg_ok = False
        for t in trace:
            if not t["tool"]:
                continue
            args = t["args"] or {}
            if all(str(args.get(k, "")).lower() == str(v).lower()
                   for k, v in case["expected_args"].items()):
                arg_ok = True
                break

    return {
        "id": case["id"], "category": case["category"], "query": case["query"],
        "expected": expected, "called": called,
        "selection_ok": selection_ok,
        "over_retrieved": over_retrieved,
        "arg_ok": arg_ok,
        "steps": len(called),
        "min_steps": len(expected),
    }


def run_variant(variant: str, cases: list[dict]) -> list[dict]:
    descriptions.apply(variant)
    print(f"\n{'#'*72}\n#  {descriptions.summary(variant)}\n{'#'*72}")

    rows = []
    for case in cases:
        session = Session(owner="rev", budget=Budget(max_tool_calls=6))
        try:
            _, trace = run(case["query"], session, max_iterations=6)
        except IterationCapExceeded:
            trace = []
        r = score_case(case, trace)
        r["cost"] = session.budget.usd_used
        rows.append(r)

        mark = "ok  " if r["selection_ok"] else "MISS"
        if r["over_retrieved"]:
            mark = "OVER"
        print(f"  {mark} {r['id']}  {case['query'][:46]:<48} "
              f"{'+'.join(r['called']) or '(none)'}")
    return rows


def report(by_variant: dict[str, list[dict]]):
    print(f"\n{'='*72}\nROUTING — selection, arguments, over-retrieval\n{'='*72}")
    print(f"{'VARIANT':<16}{'SELECTION':<13}{'ARGS':<11}{'OVER-RETR':<12}{'COST'}")
    for variant, rows in by_variant.items():
        sel = sum(r["selection_ok"] for r in rows)
        args_checked = [r for r in rows if r["arg_ok"] is not None]
        args_ok = sum(r["arg_ok"] for r in args_checked)
        no_tool = [r for r in rows if not r["expected"]]
        over = sum(r["over_retrieved"] for r in no_tool)
        print(f"{variant:<16}{sel}/{len(rows):<11}"
              f"{args_ok}/{len(args_checked):<9}"
              f"{over}/{len(no_tool):<10}"
              f"${sum(r['cost'] for r in rows):.4f}")

    # Per-category, because an aggregate hides WHICH kind of question breaks.
    cats = sorted({r["category"] for rows in by_variant.values() for r in rows})
    print(f"\n{'BY CATEGORY':<16}" + "".join(f"{c:<14}" for c in cats))
    for variant, rows in by_variant.items():
        line = f"{variant:<16}"
        for c in cats:
            sub = [r for r in rows if r["category"] == c]
            line += f"{sum(r['selection_ok'] for r in sub)}/{len(sub):<12}"
        print(line)

    # Misroutes in detail — which tool it reached for instead.
    for variant, rows in by_variant.items():
        misses = [r for r in rows if not r["selection_ok"]]
        if not misses:
            continue
        print(f"\n  misroutes — {variant}")
        for r in misses:
            print(f"    {r['id']}  wanted {r['expected'] or ['(none)']} "
                  f"got {r['called'] or ['(none)']}")
            print(f"         {r['query']}")
    print(f"\n{'='*72}")


def main():
    cases = json.load(open(EVAL_SET))
    # Four variants in a 2x2: descriptions (overlapping/separable) crossed with
    # names (descriptive/neutralised). The first run used only the top row and
    # both scored 18/18 — the names were carrying the routing on their own.
    wanted = sys.argv[1:] or ["overlapping", "separable",
                              "neutral_overlapping", "neutral_separable"]
    results = {v: run_variant(v, cases) for v in wanted}
    report(results)


if __name__ == "__main__":
    main()
