"""
eval_harness.py — Month 1, Week 4
AI Roadmap 2026 | Rev Bobba

Runs a prompt template against a labeled test set and scores the outputs
automatically, so "this prompt is better" becomes a number instead of a vibe.

Two scoring modes:
  - exact match    : objective tasks with one right answer (classification,
                     structured extraction). Cheap, deterministic, no API call.
  - LLM-as-judge   : subjective tasks (tone, summary quality). A second model
                     scores the output against a written rubric.

Vocabulary:
  - test set / eval set : fixed inputs paired with known-correct answers
  - ground truth        : the known-correct answer. Without it "accuracy" is
                          undefined.
  - regression test     : rerunning the same eval after a change, to catch a
                          score going *down* — the same idea as a unit test
                          suite, applied to prompts.

SETUP:
  python eval_harness.py
"""

import asyncio
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from llm_client import save_log
from prompt_library import get, PromptTemplate


# ── Result types ──────────────────────────────────────────────────────────────

class EvalRunError(Exception):
    """
    Raised when a run could not be validly scored — API failures, broken test
    cases. Distinct from 'the prompt scored badly', which is a normal result.

    The whole point: a run that never reached the model must never be reported
    as a score. 0/20 because the prompt is bad and 0/20 because your credit
    balance is empty look identical on a scoreboard, and only one of them
    means anything.
    """


@dataclass
class CaseResult:
    case_id: int
    input: str
    expected: str
    actual: str
    passed: bool
    score: float          # 1.0/0.0 for exact match; 1-5 scale for judge
    cost_usd: float
    latency_ms: int
    errored: bool = False   # True = the call never reached the model
    hardness: str = ""      # optional tag for per-category breakdown
    note: str = ""


@dataclass
class EvalRun:
    template_name: str
    model: str
    scorer: str
    total_cases: int
    passed: int
    errored: int
    mean_score: float
    total_cost_usd: float
    timestamp: str
    results: list[CaseResult]

    def report(self):
        pct = (self.passed / self.total_cases * 100) if self.total_cases else 0
        print(f"\n{'='*60}")
        print(f"EVAL — {self.template_name}  ({self.model}, {self.scorer})")
        print(f"{'='*60}")
        print(f"Passed:      {self.passed}/{self.total_cases}  ({pct:.0f}%)")
        print(f"Errored:     {self.errored}")
        print(f"Mean score:  {self.mean_score:.2f}")
        print(f"Total cost:  ${self.total_cost_usd:.6f}")
        for r in self.results:
            mark = "!" if r.errored else ("✓" if r.passed else "✗")
            print(f"  {mark} [{r.case_id}] expected={r.expected!r} got={r.actual!r}")
        print(f"{'='*60}")


# ── Test set loading ──────────────────────────────────────────────────────────

def load_test_set(path: str) -> list[dict]:
    """
    Test sets are JSON lists of {"input": ..., "expected": ...} objects.
    See test_sets/ticket_routing.json for the format.
    """
    with open(path) as f:
        return json.load(f)


# ── Scorers ───────────────────────────────────────────────────────────────────

def exact_match(actual: str, expected: str) -> tuple[bool, float, str]:
    """Case-insensitive, whitespace-trimmed equality. Returns (passed, score, note)."""
    a, e = actual.strip().lower(), expected.strip().lower()
    return (a == e), (1.0 if a == e else 0.0), ""


# TODO Week 4 Day 3-4: LLM-as-judge scorer
#
# async def llm_judge(actual: str, expected: str, rubric: str) -> tuple[bool, float, str]:
#     """
#     Send the output plus a written rubric to a second model and ask for a
#     1-5 score with a one-line justification.
#
#     Biases to watch for (these show up in interviews too):
#       - position bias   : judges favor whichever answer appeared first.
#                           Fix by running both orderings and averaging.
#       - verbosity bias  : judges favor longer answers regardless of quality
#       - leniency bias   : judges skew generous by default — anchor the rubric
#                           with explicit examples of a 1, a 3, and a 5
#     """
#     ...


# ── Harness ───────────────────────────────────────────────────────────────────

async def run_eval(
    template_name: str,
    test_set_path: str,
    model: str = "claude",
    scorer: str = "exact_match",
) -> EvalRun:
    template: PromptTemplate = get(template_name)
    cases = load_test_set(test_set_path)

    # Fire all cases in parallel — same asyncio pattern as Month 0's compare()
    responses = await asyncio.gather(*[
        template.run(model=model, **case["variables"]) for case in cases
    ])

    results: list[CaseResult] = []
    for i, (case, resp) in enumerate(zip(cases, responses)):
        save_log(resp)

        # An errored call never reached the model. Do NOT score it — scoring an
        # empty string against ground truth manufactures a fake 0.
        if resp.error:
            results.append(CaseResult(
                case_id=i, input=str(case["variables"]),
                expected=case["expected"], actual="",
                passed=False, score=0.0,
                cost_usd=resp.cost_usd, latency_ms=resp.latency_ms,
                errored=True, hardness=case.get("hardness", ""), note=resp.error,
            ))
            continue

        if scorer == "exact_match":
            passed, score, note = exact_match(resp.response, case["expected"])
        else:
            raise NotImplementedError(f"Scorer '{scorer}' not built yet — see TODO")

        results.append(CaseResult(
            case_id=i,
            input=str(case["variables"]),
            expected=case["expected"],
            actual=resp.response.strip(),
            passed=passed,
            score=score,
            cost_usd=resp.cost_usd,
            latency_ms=resp.latency_ms,
            errored=False,
            hardness=case.get("hardness", ""),
            note=note,
        ))

    # ── The guard ─────────────────────────────────────────────────────────────
    # Abort before building an EvalRun. A partially-failed run has no valid
    # score, so it must not produce one — not even a caveated one, because
    # caveats get skimmed past and numbers get quoted.
    errored = [r for r in results if r.errored]
    if errored:
        first = errored[0].note
        raise EvalRunError(
            f"{template_name}: {len(errored)}/{len(results)} calls failed — "
            f"run not scored.\nFirst error: {first}"
        )

    run = EvalRun(
        template_name=template_name,
        model=model,
        scorer=scorer,
        total_cases=len(results),
        passed=sum(r.passed for r in results),
        errored=0,
        mean_score=(sum(r.score for r in results) / len(results)) if results else 0.0,
        total_cost_usd=sum(r.cost_usd for r in results),
        timestamp=datetime.now().isoformat(),
        results=results,
    )
    save_eval_run(run)
    return run


def save_eval_run(run: EvalRun, log_dir: str = "logs"):
    Path(log_dir).mkdir(exist_ok=True)
    path = Path(log_dir) / "eval_runs.jsonl"
    with open(path, "a") as f:
        f.write(json.dumps(asdict(run)) + "\n")


# ── Comparing prompt versions ─────────────────────────────────────────────────

async def compare_templates(names: list[str], test_set_path: str, model: str = "claude"):
    """
    Run several prompt versions against the same test set and print a scoreboard.
    This is the regression test: did your 'improvement' actually move the number?
    """
    try:
        runs = [await run_eval(n, test_set_path, model=model) for n in names]
    except EvalRunError as e:
        # Print no scoreboard at all. A scoreboard implies the numbers mean
        # something; here they don't.
        print(f"\n{'='*60}")
        print("RUN ABORTED — no valid scores produced")
        print(f"{'='*60}")
        print(e)
        print("\nFix the error above and rerun. Nothing was scored.")
        return []

    print(f"\n{'='*60}")
    print("SCOREBOARD")
    print(f"{'='*60}")
    print(f"{'Template':<32}{'Passed':<12}{'Mean':<8}{'Cost'}")
    for r in runs:
        print(f"{r.template_name:<32}{r.passed}/{r.total_cases:<10}"
              f"{r.mean_score:<8.2f}${r.total_cost_usd:.6f}")

    # Per-hardness breakdown — the aggregate hides WHICH kind of hard case a
    # prompt handles. A prompt can win overall while losing badly on one class.
    tags = sorted({r.hardness for run in runs for r in run.results if r.hardness})
    if tags:
        print(f"\n{'BY HARDNESS':<32}" + "".join(f"{t:<14}" for t in tags))
        for run in runs:
            row = f"{run.template_name:<32}"
            for t in tags:
                sub = [r for r in run.results if r.hardness == t]
                row += f"{sum(r.passed for r in sub)}/{len(sub):<12}"
            print(row)

    best = max(runs, key=lambda r: r.mean_score)
    tied = [r for r in runs if r.mean_score == best.mean_score]
    if len(tied) > 1:
        names_ = ", ".join(r.template_name for r in tied)
        print(f"\n⚖️   Tie at {best.mean_score:.2f}: {names_}")
        print("    A tie means this test set can't tell these prompts apart —")
        print("    that's a finding about your eval, not about the prompts.")
    else:
        print(f"\n🏆  Best: {best.template_name} ({best.mean_score:.2f})")
    return runs


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    # Flip between "claude" and "openai" here. Worth running both — the same
    # prompt does not necessarily score the same on different models, which is
    # why PromptTemplate records tuned_for.
    MODEL = "claude"

    await compare_templates(
        ["hard_zero_shot", "hard_zero_shot_rules",
         "hard_zero_shot_rules_ablated", "hard_few_shot"],
        "test_sets/ticket_routing_hard.json",
        model=MODEL,
    )


if __name__ == "__main__":
    asyncio.run(main())
