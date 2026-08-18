"""
chaining.py — Month 1, Week 3

Prompt chaining: split one task across sequential prompts, feeding each output
into the next.

THE HYPOTHESIS
--------------
A single review prompt asks for several things simultaneously — find the
problems, rate their severity, explain them, suggest fixes. Those objectives
compete for a finite output budget. Tokens spent explaining issue #1 are tokens
not spent finding issue #6, which is exactly how the "friendly" persona traded
coverage for tone in Experiment 2.

The chain separates them:

    step 1   enumerate ONLY — no severity, no explanation, no fixes
    step 2   take that list and assess it

Step 1 has one objective and nothing to trade against. Step 2 receives a
complete list rather than generating and judging at the same time.

WHAT IT SHOULD COST
-------------------
Two calls instead of one, and step 2's prompt carries step 1's output. So
roughly 2x+ the tokens and 2x the latency (the calls are sequential — step 2
cannot start until step 1 finishes). The question is whether the coverage gain
is worth that.

SCORING
-------
Reuses checklist_scorer's grounded judge unchanged, so chained and single-prompt
reviews are graded identically.

Run:  python chaining.py
"""

import asyncio
import json

from checklist_scorer import judge_issue, save
from llm_client import save_log
from prompt_library import get


async def run_single(template_name: str, snippet: dict, model: str):
    """Baseline: one prompt does everything."""
    resp = await get(template_name).run(model=model, **snippet["variables"])
    if resp.error:
        raise RuntimeError(resp.error)
    save_log(resp)
    return resp.response, resp.cost_usd, resp.tokens_out, 1


async def run_chained(snippet: dict, model: str):
    """Two prompts: enumerate, then assess."""
    code = snippet["variables"]["code"]

    step1 = await get("review_chain_enumerate").run(model=model, code=code)
    if step1.error:
        raise RuntimeError(step1.error)
    save_log(step1)

    step2 = await get("review_chain_assess").run(
        model=model, code=code, problems=step1.response)
    if step2.error:
        raise RuntimeError(step2.error)
    save_log(step2)

    return (step2.response,
            step1.cost_usd + step2.cost_usd,
            step1.tokens_out + step2.tokens_out,
            2)


async def score(review: str, snippet: dict):
    """Grade one review against the planted issues. Same judge as Experiment 2."""
    verdicts = await asyncio.gather(*[
        judge_issue(review, i) for i in snippet["planted_issues"]
    ])
    found = [v for v in verdicts if v.found]
    crit = [v for v in verdicts if v.severity_truth in ("critical", "high")]
    sev_ok = [v for v in found if v.severity_given == v.severity_truth]
    judge_cost = sum(v.cost_usd for v in verdicts)
    return {
        "recall": len(found) / len(verdicts),
        "crit_recall": (len([v for v in crit if v.found]) / len(crit)) if crit else 0.0,
        "sev_agree": (len(sev_ok) / len(found)) if found else 0.0,
        "found": len(found), "planted": len(verdicts),
        "judge_cost": judge_cost, "verdicts": verdicts,
    }


async def arm(name: str, snippets: list[dict], model: str):
    rows = []
    for snip in snippets:
        if name == "chained":
            review, cost, tokens, calls = await run_chained(snip, model)
        else:
            review, cost, tokens, calls = await run_single(name, snip, model)
        s = await score(review, snip)
        s.update({"snippet": snip["name"], "review_cost": cost,
                  "tokens": tokens, "calls": calls})
        rows.append(s)

    n = len(rows)
    return {
        "name": name, "model": model, "rows": rows,
        "recall": sum(r["recall"] for r in rows) / n,
        "crit_recall": sum(r["crit_recall"] for r in rows) / n,
        "sev_agree": sum(r["sev_agree"] for r in rows) / n,
        "found": sum(r["found"] for r in rows),
        "planted": sum(r["planted"] for r in rows),
        "tokens": sum(r["tokens"] for r in rows),
        "calls": sum(r["calls"] for r in rows),
        "cost": sum(r["review_cost"] + r["judge_cost"] for r in rows),
    }


def report(arms):
    print(f"\n{'='*80}")
    print("PROMPT CHAINING vs SINGLE PROMPT — code review")
    print(f"{'='*80}")
    print(f"{'ARM':<24}{'FOUND':<10}{'RECALL':<10}{'CRIT':<9}{'SEV':<9}"
          f"{'CALLS':<8}{'TOKENS':<9}{'COST'}")
    for a in arms:
        print(f"{a['name']:<24}{a['found']}/{a['planted']:<7}"
              f"{a['recall']:<10.0%}{a['crit_recall']:<9.0%}{a['sev_agree']:<9.0%}"
              f"{a['calls']:<8}{a['tokens']:<9}${a['cost']:.6f}")

    print(f"\n  per snippet — issues found")
    names = [r["snippet"] for r in arms[0]["rows"]]
    print(f"    {'snippet':<16}" + "".join(f"{a['name'][:14]:<16}" for a in arms))
    for i, sn in enumerate(names):
        line = f"    {sn:<16}"
        for a in arms:
            r = a["rows"][i]
            line += f"{r['found']}/{r['planted']:<14}"
        print(line)

    print(f"\n  misses")
    for a in arms:
        missed = [(r["snippet"], v.issue_id, v.severity_truth)
                  for r in a["rows"] for v in r["verdicts"] if not v.found]
        label = f"{a['name']}:"
        print(f"    {label:<24}" + (", ".join(f"{i}({s})" for _, i, s in missed)
                                     if missed else "none"))
    print(f"\n{'='*80}")


async def main(model: str = "claude"):
    snippets = json.load(open("test_sets/code_review.json"))
    arms = []
    # Three arms so chaining is isolated from the rubric:
    #   strict          no rubric, one call    (Experiment 2 baseline)
    #   strict_rubric   rubric,    one call    (controls for the rubric)
    #   chained         rubric,    two calls   (chaining vs strict_rubric)
    for name in ["code_review_strict", "code_review_strict_rubric", "chained"]:
        arms.append(await arm(name, snippets, model))
    report(arms)


if __name__ == "__main__":
    asyncio.run(main())
