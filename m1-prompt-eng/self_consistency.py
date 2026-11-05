"""
self_consistency.py — Month 1, Week 3

Run the same chain-of-thought prompt N times at temperature > 0 and take the
majority answer.

WHY TEMPERATURE MATTERS HERE
----------------------------
Every other experiment this month runs at temperature 0 for reproducibility.
Self-consistency is the one technique that REQUIRES variance — at temperature 0
all N samples are byte-identical and the vote is meaningless. This is the case
the `temperature` parameter on PromptTemplate.run() was left configurable for.

THREE ARMS
----------
  single_temp0   CoT, temp 0.0, 1 sample   — the prompt's best single shot
  single_temp07  CoT, temp 0.7, 1 sample   — one production-like draw
  self_consist   CoT, temp 0.7, 5 samples, majority vote

The comparison that matters is arm 3 vs arm 2: same temperature, 1 sample
versus 5. Arm 1 is a reference point for what a single deterministic shot buys.

THE SECOND MEASUREMENT, WHICH MAY MATTER MORE
---------------------------------------------
Beyond accuracy, this records AGREEMENT — how many of the 5 samples landed on
the majority answer. 5/5 means the model is stable on that problem; 2/5 means it
is guessing.

If agreement correlates with correctness, you have a cheap confidence signal
that costs nothing extra once you are already sampling: route low-agreement
cases to a human or a stronger model. That is a genuine use for self-consistency
beyond the accuracy bump, and it partly addresses the calibration problem —
models cannot reliably report their own uncertainty, but disagreement across
samples is an external measurement of it.

Run:  python self_consistency.py
"""

import asyncio
import json
import re
from collections import Counter

from prompt_library import get

N_SAMPLES = 5
TEMP = 0.7
TEMPLATE = "math_cot"
TEST_SET = "test_sets/math_hard.json"


def extract_answer(raw: str) -> str | None:
    """
    Pull the final number from a chain-of-thought response.

    Same logic as eval_harness.numeric_match, but returns the value rather than
    a score, because the vote needs the answers themselves.
    """
    m = re.search(r"ANSWER:\s*\$?(-?[\d,]+(?:\.\d+)?)", raw, re.I)
    if m:
        got = m.group(1)
    else:
        nums = re.findall(r"-?[\d,]+(?:\.\d+)?", raw.replace("$", ""))
        if not nums:
            return None
        got = nums[-1]
    try:
        # Normalise so "63.60" and "63.6" vote together.
        return f"{float(got.replace(',', '')):.4f}".rstrip("0").rstrip(".")
    except ValueError:
        return None


def correct(answer: str | None, expected: str) -> bool:
    if answer is None:
        return False
    try:
        return abs(float(answer) - float(expected)) < 0.011
    except ValueError:
        return False


async def run_case(case: dict, n: int, temperature: float, model: str):
    """Sample the template n times; return (majority_answer, agreement, cost)."""
    template = get(TEMPLATE)
    responses = await asyncio.gather(*[
        template.run(model=model, temperature=temperature, **case["variables"])
        for _ in range(n)
    ])
    cost = sum(r.cost_usd for r in responses)
    answers = [extract_answer(r.response) for r in responses]
    valid = [a for a in answers if a is not None]
    if not valid:
        return None, 0, cost
    winner, votes = Counter(valid).most_common(1)[0]
    return winner, votes / n, cost


async def arm(name: str, n: int, temperature: float, model: str):
    cases = json.load(open(TEST_SET))
    results = await asyncio.gather(*[
        run_case(c, n, temperature, model) for c in cases
    ])

    rows, cost = [], 0.0
    for case, (ans, agreement, c) in zip(cases, results):
        cost += c
        ok = correct(ans, case["expected"])
        rows.append({"hardness": case["hardness"], "ok": ok,
                     "agreement": agreement, "answer": ans,
                     "expected": case["expected"]})
    return {"name": name, "model": model, "rows": rows, "cost": cost,
            "passed": sum(r["ok"] for r in rows), "total": len(rows)}


def report(arms: list[dict]):
    print(f"\n{'='*76}")
    print(f"SELF-CONSISTENCY — {TEMPLATE} on {TEST_SET.split('/')[-1]}")
    print(f"{'='*76}")
    print(f"{'MODEL':<10}{'ARM':<18}{'PASSED':<10}{'COST':<13}{'vs 1-SHOT'}")
    base = {}
    for a in arms:
        if a["name"] == "single_temp07":
            base[a["model"]] = a["cost"]
    for a in arms:
        mult = f"{a['cost']/base[a['model']]:.1f}x" if a["model"] in base else "-"
        print(f"{a['model']:<10}{a['name']:<18}{a['passed']}/{a['total']:<8}"
              f"${a['cost']:<12.6f}{mult}")

    # Agreement vs correctness — is disagreement a usable confidence signal?
    for a in arms:
        if a["name"] != "self_consist":
            continue
        print(f"\n  agreement breakdown — {a['model']}")
        print(f"    {'agreement':<12}{'cases':<8}{'correct'}")
        buckets = {}
        for r in a["rows"]:
            k = f"{int(r['agreement']*N_SAMPLES)}/{N_SAMPLES}"
            p, t = buckets.get(k, (0, 0))
            buckets[k] = (p + int(r["ok"]), t + 1)
        for k in sorted(buckets, reverse=True):
            p, t = buckets[k]
            print(f"    {k:<12}{t:<8}{p}/{t}")

        wrong = [r for r in a["rows"] if not r["ok"]]
        if wrong:
            print(f"\n    failures ({a['model']})")
            for r in wrong:
                print(f"      {r['hardness']:<18} got {r['answer']:<10} "
                      f"want {r['expected']:<10} agreement {r['agreement']:.0%}")
    print(f"\n{'='*76}")


async def main():
    arms = []
    for model in ["claude"]:
        arms.append(await arm("single_temp0", 1, 0.0, model))
        arms.append(await arm("single_temp07", 1, TEMP, model))
        arms.append(await arm("self_consist", N_SAMPLES, TEMP, model))
    report(arms)


if __name__ == "__main__":
    asyncio.run(main())
