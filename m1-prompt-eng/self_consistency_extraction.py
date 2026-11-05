"""
self_consistency_extraction.py — Month 1, Week 3 (Experiment 7b)

Self-consistency applied to a failure that actually reproduces.

WHY NOT MATH
------------
Experiment 7a built a "hard" math set and the model scored 12/12 with 5/5
agreement. Nothing to vote on. The problems were hard for humans, not for the
model — the same mistake Experiment 6 already identified.

Rather than invent more math, this reuses a failure that has reproduced on every
single run: extraction arithmetic. Both Claude and GPT-4o fail both
`arithmetic_load` cases, on prose JSON and on tool calling, at temperature 0.
Reliable failure is exactly what self-consistency needs.

THE QUESTION THIS ANSWERS
-------------------------
Is the arithmetic error SYSTEMATIC or RANDOM?

  systematic  the model makes the same wrong computation every time.
              Majority vote returns the same wrong answer 5 times. No help.
  random      each sample errs differently, and the correct answer is the most
              common single outcome. Majority vote recovers it.

Self-consistency only rescues random error. If the model reliably mis-adds the
same way, sampling five times buys five identical mistakes at five times the
price. That distinction is the whole value of running this.

It also finally tests the agreement-as-confidence hypothesis: with real failures
present, do low-agreement cases correlate with wrong answers?

Run:  python self_consistency_extraction.py
"""

import asyncio
import json
from collections import Counter

from prompt_library import get
from schemas import HardOrder

N_SAMPLES = 5
TEMP = 0.7
TEMPLATE = "extract_hard"
TEST_SET = "test_sets/entity_extraction_hard.json"


def canonical(raw: str) -> str | None:
    """
    Normalise a response to a canonical JSON string so identical objects vote
    together regardless of key order or whitespace. Returns None if unparseable.
    """
    import re
    s = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    s = re.sub(r"\s*```$", "", s)
    m = re.search(r"\{.*\}", s, re.S)
    if not m:
        return None
    try:
        return json.dumps(json.loads(m.group(0)), sort_keys=True)
    except json.JSONDecodeError:
        return None


def subtotal_of(payload: str | None) -> float | None:
    if payload is None:
        return None
    try:
        return float(json.loads(payload).get("subtotal"))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


async def run_case(case: dict, n: int, temperature: float, model: str):
    template = get(TEMPLATE)
    responses = await asyncio.gather(*[
        template.run(model=model, temperature=temperature, **case["variables"])
        for _ in range(n)
    ])
    cost = sum(r.cost_usd for r in responses)
    objs = [canonical(r.response) for r in responses]
    valid = [o for o in objs if o is not None]
    if not valid:
        return None, 0.0, cost, []
    winner, votes = Counter(valid).most_common(1)[0]
    subtotals = [subtotal_of(o) for o in valid]
    return winner, votes / n, cost, subtotals


def scores_ok(payload: str | None, expected: dict) -> tuple[bool, str]:
    """Validate against HardOrder, then compare values. Returns (ok, note)."""
    from pydantic import ValidationError
    if payload is None:
        return False, "unparseable"
    try:
        obj = HardOrder.model_validate(json.loads(payload))
    except ValidationError as e:
        first = e.errors()[0]
        loc = ".".join(map(str, first["loc"])) or "(object)"
        return False, f"{loc}: {first['msg'][:44]}"
    got = json.loads(obj.model_dump_json())
    for k, v in expected.items():
        a = got.get(k)
        if isinstance(a, (int, float)) and isinstance(v, (int, float)):
            if abs(float(a) - float(v)) > 0.01:
                return False, f"{k}: got {a}, want {v}"
        elif a != v:
            return False, f"{k} mismatch"
    return True, ""


async def arm(name: str, n: int, temperature: float, model: str):
    cases = json.load(open(TEST_SET))
    results = await asyncio.gather(*[
        run_case(c, n, temperature, model) for c in cases
    ])
    rows, cost = [], 0.0
    for case, (payload, agreement, c, subtotals) in zip(cases, results):
        cost += c
        ok, note = scores_ok(payload, json.loads(case["expected"]))
        rows.append({"hardness": case["hardness"], "ok": ok, "note": note,
                     "agreement": agreement, "subtotals": subtotals})
    return {"name": name, "model": model, "rows": rows, "cost": cost,
            "passed": sum(r["ok"] for r in rows), "total": len(rows)}


def report(arms):
    print(f"\n{'='*78}")
    print(f"SELF-CONSISTENCY ON EXTRACTION — {TEMPLATE}")
    print(f"{'='*78}")
    print(f"{'MODEL':<10}{'ARM':<18}{'PASSED':<10}{'COST':<14}{'MULT'}")
    base = {a["model"]: a["cost"] for a in arms if a["name"] == "single_temp07"}
    for a in arms:
        m = f"{a['cost']/base[a['model']]:.1f}x" if a["model"] in base else "-"
        print(f"{a['model']:<10}{a['name']:<18}{a['passed']}/{a['total']:<8}"
              f"${a['cost']:<13.6f}{m}")

    for a in arms:
        if a["name"] != "self_consist":
            continue
        print(f"\n  agreement vs correctness — {a['model']}")
        print(f"    {'agreement':<12}{'cases':<8}{'correct'}")
        b = {}
        for r in a["rows"]:
            k = f"{round(r['agreement']*N_SAMPLES)}/{N_SAMPLES}"
            p, t = b.get(k, (0, 0))
            b[k] = (p + int(r["ok"]), t + 1)
        for k in sorted(b, reverse=True):
            p, t = b[k]
            print(f"    {k:<12}{t:<8}{p}/{t}")

        print(f"\n    arithmetic cases — the 5 sampled subtotals")
        for r in a["rows"]:
            if r["hardness"] != "arithmetic_load":
                continue
            uniq = sorted(set(s for s in r["subtotals"] if s is not None))
            print(f"      agreement {r['agreement']:.0%}  distinct subtotals: {uniq}")
            print(f"        -> {'PASS' if r['ok'] else 'FAIL: ' + r['note']}")
    print(f"\n{'='*78}")


async def main():
    arms = []
    for model in ["claude"]:
        arms.append(await arm("single_temp0", 1, 0.0, model))
        arms.append(await arm("single_temp07", 1, TEMP, model))
        arms.append(await arm("self_consist", N_SAMPLES, TEMP, model))
    report(arms)


if __name__ == "__main__":
    asyncio.run(main())
