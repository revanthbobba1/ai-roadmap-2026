"""
run_review.py — Month 1, Week 1 Day 3-4

Runs the three code-review personas against one snippet and prints the outputs
side by side.

This exists because eval_harness.py CANNOT score this task. Review output is
prose; there's no string to compare against ground truth, so exact_match is
useless. For now: read the three outputs and judge with your own eyes.

That's not a workaround, it's the honest first step — you have to know what
"better" looks like before you can automate scoring it.

Run:  python run_review.py            # first snippet
      python run_review.py 1          # second snippet
"""

import asyncio
import json
import sys

from prompt_library import get

TEMPLATES = ["code_review_neutral", "code_review_strict", "code_review_friendly"]


async def main(snippet_idx: int = 0, model: str = "claude"):
    snippets = json.load(open("test_sets/code_review.json"))
    snip = snippets[snippet_idx]

    print("=" * 70)
    print(f"SNIPPET: {snip['name']}")
    print("=" * 70)
    print(snip["variables"]["code"])
    print(f"Planted issues ({len(snip['planted_issues'])}):")
    for iss in snip["planted_issues"]:
        print(f"  [{iss['severity']:<8}] {iss['id']:<20} {iss['desc']}")

    results = await asyncio.gather(*[
        get(name).run(model=model, **snip["variables"]) for name in TEMPLATES
    ])

    for name, r in zip(TEMPLATES, results):
        print()
        print("=" * 70)
        print(f"{name}   ({r.tokens_out} tokens out, ${r.cost_usd:.6f})")
        print("=" * 70)
        print(r.error if r.error else r.response)

    print()
    print("=" * 70)
    print(f"{'TEMPLATE':<26}{'TOKENS OUT':<14}{'COST'}")
    for name, r in zip(TEMPLATES, results):
        print(f"{name:<26}{r.tokens_out:<14}${r.cost_usd:.6f}")
    print("=" * 70)


if __name__ == "__main__":
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    asyncio.run(main(idx))
