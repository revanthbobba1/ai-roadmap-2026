"""
regression.py — Month 1, Week 4

One command that runs every experiment against a saved baseline and reports
which scores moved.

NOT ONE SCORE — ONE COMMAND
---------------------------
The experiments measure different things: exact-match classification, numeric
answers, schema validation, issue recall from an LLM judge. Nothing is averaged.
Each experiment keeps its own metric and its own recorded baseline, and the
comparison is always "this experiment vs. what this experiment scored last
time."

Same structure as a test suite. `pytest` runs hundreds of tests checking
unrelated things; it doesn't combine them into a number, it reports which ones
changed.

WHAT IT'S FOR
-------------
1. You change one prompt      — did anything else move?
2. The model version changes  — did behaviour drift? This is the strongest
                                case. A provider ships a new model and prompts
                                quietly behave differently; without a baseline
                                you find out from users.
3. Someone else runs the repo — including you in three months.

This is the "regression gate" idea: an eval set becomes infrastructure rather
than a one-time exercise once it runs automatically and blocks on a drop.

USAGE
-----
  python regression.py              run and compare against baselines.json
  python regression.py --update     run and OVERWRITE baselines with current
  python regression.py --list       show configs and estimated call count

Exit code 1 if any experiment regressed, so it can gate CI.

COST: roughly 250 API calls for a full run. Use --only to run a subset.
"""

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

BASELINE_FILE = Path("baselines.json")
TOLERANCE = 0.001          # float noise, not a real change


@dataclass
class Experiment:
    name: str
    metric: str            # what the number means — NOT comparable across rows
    calls: int             # rough API call count, for cost awareness
    run: Callable[[], Awaitable[float]]


# ── Adapters ──────────────────────────────────────────────────────────────────
# Each existing script has its own return shape. These wrap them into a single
# float so the runner can treat them uniformly. The scoring logic is untouched —
# this is orchestration only.

async def _eval_harness(template: str, test_set: str, scorer: str,
                        model: str = "claude") -> float:
    from eval_harness import run_eval
    run = await run_eval(template, f"test_sets/{test_set}", model=model, scorer=scorer)
    return run.mean_score


async def _tool_calling(model: str = "claude") -> float:
    import tool_calling
    rows = await tool_calling.run(model)
    return sum(1 for _, ok, _, _ in rows if ok) / len(rows)


async def _retry(arm_name: str, model: str = "claude") -> float:
    from retry_loop import DESC_FULL, DESC_NO_SUBTOTAL, MAX_ATTEMPTS, arm
    from schemas import HardOrder, OrderNoSubtotal
    if arm_name == "retry":
        r = await arm("retry", model, HardOrder, DESC_FULL, MAX_ATTEMPTS, False)
    else:
        r = await arm("computed", model, OrderNoSubtotal, DESC_NO_SUBTOTAL, 1, True)
    return r["passed"] / r["total"]


async def _code_review(template: str, model: str = "claude") -> float:
    import chaining
    snippets = json.load(open("test_sets/code_review.json"))
    r = await chaining.arm(template, snippets, model)
    return r["recall"]


# ── Registry ──────────────────────────────────────────────────────────────────
# Chosen to cover every scorer and every mechanism, not every template ever
# written. A regression suite that costs $2 to run gets run; one that costs $20
# does not.

EXPERIMENTS: list[Experiment] = [
    Experiment("ticket_routing/no_policy", "exact_match", 24,
               lambda: _eval_harness("hard_zero_shot",
                                     "ticket_routing_hard.json", "exact_match")),
    Experiment("ticket_routing/prose_rules", "exact_match", 24,
               lambda: _eval_harness("hard_zero_shot_rules",
                                     "ticket_routing_hard.json", "exact_match")),
    Experiment("ticket_routing/few_shot", "exact_match", 24,
               lambda: _eval_harness("hard_few_shot",
                                     "ticket_routing_hard.json", "exact_match")),

    Experiment("math/direct", "numeric_match", 16,
               lambda: _eval_harness("math_direct",
                                     "math_word_problems.json", "numeric_match")),
    Experiment("math/cot", "numeric_match", 16,
               lambda: _eval_harness("math_cot",
                                     "math_word_problems.json", "numeric_match")),

    Experiment("extraction/flat", "pydantic", 12,
               lambda: _eval_harness("extract_plain",
                                     "entity_extraction.json", "pydantic_match")),
    Experiment("extraction/hard_prose", "hard_order", 10,
               lambda: _eval_harness("extract_hard",
                                     "entity_extraction_hard.json",
                                     "hard_order_match")),
    Experiment("extraction/hard_tools", "hard_order", 10,
               lambda: _tool_calling()),
    Experiment("extraction/retry", "hard_order", 14,
               lambda: _retry("retry")),
    Experiment("extraction/computed", "hard_order", 10,
               lambda: _retry("computed")),

    Experiment("code_review/strict", "issue_recall", 24,
               lambda: _code_review("code_review_strict")),
    Experiment("code_review/strict_rubric", "issue_recall", 24,
               lambda: _code_review("code_review_strict_rubric")),
]


# ── Runner ────────────────────────────────────────────────────────────────────

def load_baselines() -> dict:
    if not BASELINE_FILE.exists():
        return {}
    return json.loads(BASELINE_FILE.read_text())


def save_baselines(scores: dict):
    payload = {
        "recorded": datetime.now().isoformat(timespec="seconds"),
        "scores": scores,
    }
    BASELINE_FILE.write_text(json.dumps(payload, indent=2) + "\n")


async def main(update: bool, only: str | None):
    experiments = [e for e in EXPERIMENTS if not only or only in e.name]
    if not experiments:
        print(f"no experiments match {only!r}")
        return 1

    baselines = load_baselines().get("scores", {})
    results, regressed = {}, []

    print(f"running {len(experiments)} experiments "
          f"(~{sum(e.calls for e in experiments)} calls)\n")
    print(f"{'EXPERIMENT':<32}{'METRIC':<16}{'BASE':<8}{'NOW':<8}{'STATUS'}")
    print("-" * 78)

    for e in experiments:
        try:
            score = await e.run()
        except Exception as exc:
            print(f"{e.name:<32}{e.metric:<16}{'':<8}{'':<8}ERROR {str(exc)[:28]}")
            regressed.append(e.name)
            continue

        results[e.name] = {"metric": e.metric, "value": round(score, 4)}
        base = baselines.get(e.name, {}).get("value")

        if base is None:
            status = "new"
        elif score < base - TOLERANCE:
            status = f"REGRESSED {score - base:+.0%}"
            regressed.append(e.name)
        elif score > base + TOLERANCE:
            status = f"improved {score - base:+.0%}"
        else:
            status = "ok"

        base_s = f"{base:.2f}" if base is not None else "-"
        print(f"{e.name:<32}{e.metric:<16}{base_s:<8}{score:<8.2f}{status}")

    print("-" * 78)
    if update:
        save_baselines(results)
        print(f"baselines written to {BASELINE_FILE}")
        return 0

    print(f"{len(results) - len(regressed)}/{len(results)} stable, "
          f"{len(regressed)} regressed")
    if regressed:
        print("regressions: " + ", ".join(regressed))
    return 1 if regressed else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--update", action="store_true",
                   help="overwrite baselines with the current run")
    p.add_argument("--only", help="substring filter on experiment name")
    p.add_argument("--list", action="store_true", help="show configs and exit")
    args = p.parse_args()

    if args.list:
        print(f"{'EXPERIMENT':<32}{'METRIC':<16}{'CALLS'}")
        for e in EXPERIMENTS:
            print(f"{e.name:<32}{e.metric:<16}{e.calls}")
        print(f"\n{len(EXPERIMENTS)} experiments, "
              f"~{sum(e.calls for e in EXPERIMENTS)} calls per full run")
        sys.exit(0)

    sys.exit(asyncio.run(main(args.update, args.only)))
