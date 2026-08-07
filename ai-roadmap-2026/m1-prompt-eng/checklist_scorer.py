"""
checklist_scorer.py — Month 1, Week 1 Day 3-4

A grounded LLM-as-judge for tasks whose output is prose and therefore can't be
scored by exact_match.

THE DESIGN DECISION THAT MAKES THIS WORK
----------------------------------------
There are two ways to use a model as a judge:

  1. Holistic   "Rate this code review 1-5 for thoroughness."
                No ground truth. The judge exercises taste. Maximum exposure to
                position bias, verbosity bias, and leniency bias — it will
                reward whichever output is best-presented.

  2. Grounded   "Here is one specific defect. Does this review identify it?
                Answer YES or NO."
                Asked once per known defect. The judge does a factual lookup
                against something YOU defined, not a taste judgement.

This module implements (2). The judge never decides what "good" means — you
decided that when you wrote planted_issues. The judge only checks presence.

An automated scorer is not more correct than a human. It is more CONSISTENT and
it SCALES. Its accuracy comes entirely from the quality of the ground truth.

Metrics produced:
  issue_recall        found / planted            — did it catch the defects?
  critical_recall     same, restricted to critical+high — did it catch the ones
                      that matter? An 80% recall that missed the SQL injection
                      is worse than a 60% that caught it.
  severity_agreement  of the issues it found, how often did it rate the
                      severity the same way the ground truth does?
  extra_issues        things it flagged that aren't on the list — not scored,
                      since these may be legitimate findings or noise.

Run:  python checklist_scorer.py
"""

import asyncio
import json
import re
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path

from llm_client import call_claude, save_log
from prompt_library import get

JUDGE_MODEL = "claude-haiku-4-5"
SEVERITIES = ["critical", "high", "medium", "trivial"]


# ── The judge prompt ──────────────────────────────────────────────────────────

# Severity defined by CONSEQUENCE, not by vibes. The first run had severity
# agreement of 20-57% across every template — when all raters disagree with your
# ground truth, the ground truth is the outlier. The real defect was that
# "trivial" and "medium" were never defined, so the judge was mapping the
# review's colour-coding onto an undefined scale and inventing the difference.
SEVERITY_RUBRIC = """critical - exploitable security hole, data loss, or corruption
high     - causes incorrect behaviour or a crash during normal use
medium   - causes problems under some conditions, or significantly harms
           maintainability or testability
trivial  - style or cleanliness only; no behavioural impact whatsoever"""

JUDGE_TEMPLATE = """You are grading a code review against a known defect.

DEFECT THAT EXISTS IN THE CODE:
{issue_desc}

THE CODE REVIEW TO GRADE:
---
{review}
---

Question 1: Does the review identify this specific defect? It need not use the
same wording, but it must clearly describe THIS problem — not a different
problem that happens to be nearby. Silently fixing it in a rewritten code block
WITHOUT describing it as a problem does NOT count as identifying it. If the only
evidence is corrected code with no accompanying explanation, answer NO.

Question 2: If it identified the defect, how urgent did the REVIEW treat it as?
Judge by how the review itself framed it — its labels, ordering, and language —
and place that on this scale:

{rubric}

Answer "none" if the review mentioned the defect but gave no urgency signal.
Do not substitute your own opinion of the defect's true severity; report how the
review presented it.

Respond in exactly this format and nothing else:
FOUND: YES or NO
SEVERITY: critical, high, medium, trivial, or none"""


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class IssueVerdict:
    issue_id: str
    severity_truth: str
    found: bool
    severity_given: str
    cost_usd: float


@dataclass
class ReviewScore:
    template_name: str
    snippet: str
    issue_recall: float
    critical_recall: float
    severity_agreement: float
    found: int
    planted: int
    tokens_out: int
    review_cost_usd: float
    judge_cost_usd: float
    timestamp: str
    review_text: str = ""   # kept so a judge verdict can be audited, not guessed at
    verdicts: list[IssueVerdict] = field(default_factory=list)


# ── Judging ───────────────────────────────────────────────────────────────────

def _parse(raw: str) -> tuple[bool, str]:
    """Pull FOUND/SEVERITY out of the judge's reply. Defensive: models drift."""
    found = bool(re.search(r"FOUND:\s*YES", raw, re.I))
    m = re.search(r"SEVERITY:\s*(critical|high|medium|trivial|none)", raw, re.I)
    return found, (m.group(1).lower() if m else "none")


async def judge_issue(review: str, issue: dict) -> IssueVerdict:
    """Ask one binary, grounded question about one defect."""
    prompt = JUDGE_TEMPLATE.format(
        issue_desc=issue["desc"], review=review, rubric=SEVERITY_RUBRIC)
    resp = await call_claude(
        prompt,
        system_prompt="You are a precise grader. Follow the output format exactly.",
        model=JUDGE_MODEL,
        temperature=0.0,          # grading should be deterministic
        max_tokens=32,
    )
    if resp.error:
        raise RuntimeError(f"Judge call failed: {resp.error}")
    found, sev = _parse(resp.response)
    return IssueVerdict(
        issue_id=issue["id"],
        severity_truth=issue["severity"],
        found=found,
        severity_given=sev,
        cost_usd=resp.cost_usd,
    )


async def score_review(template_name: str, snippet: dict, model: str = "claude") -> ReviewScore:
    """Run one template on one snippet, then grade it issue by issue."""
    resp = await get(template_name).run(model=model, **snippet["variables"])
    if resp.error:
        raise RuntimeError(f"Review call failed: {resp.error}")
    save_log(resp)

    issues = snippet["planted_issues"]
    verdicts = await asyncio.gather(*[judge_issue(resp.response, i) for i in issues])

    found = [v for v in verdicts if v.found]
    crit = [v for v in verdicts if v.severity_truth in ("critical", "high")]
    crit_found = [v for v in crit if v.found]
    sev_ok = [v for v in found if v.severity_given == v.severity_truth]

    return ReviewScore(
        template_name=template_name,
        snippet=snippet["name"],
        issue_recall=len(found) / len(issues),
        critical_recall=(len(crit_found) / len(crit)) if crit else 0.0,
        severity_agreement=(len(sev_ok) / len(found)) if found else 0.0,
        found=len(found),
        planted=len(issues),
        tokens_out=resp.tokens_out,
        review_cost_usd=resp.cost_usd,
        judge_cost_usd=sum(v.cost_usd for v in verdicts),
        timestamp=datetime.now().isoformat(),
        review_text=resp.response,
        verdicts=list(verdicts),
    )


# ── Reporting ─────────────────────────────────────────────────────────────────

def report(scores: list[ReviewScore]):
    by_template: dict[str, list[ReviewScore]] = {}
    for s in scores:
        by_template.setdefault(s.template_name, []).append(s)

    print(f"\n{'='*78}")
    print("CHECKLIST SCORER — grounded LLM-as-judge")
    print(f"{'='*78}")
    print(f"{'TEMPLATE':<26}{'RECALL':<10}{'CRIT':<10}{'SEV AGREE':<12}{'TOKENS':<10}{'COST'}")
    for name, ss in by_template.items():
        n = len(ss)
        print(f"{name:<26}"
              f"{sum(s.issue_recall for s in ss)/n:<10.0%}"
              f"{sum(s.critical_recall for s in ss)/n:<10.0%}"
              f"{sum(s.severity_agreement for s in ss)/n:<12.0%}"
              f"{sum(s.tokens_out for s in ss)//n:<10}"
              f"${sum(s.review_cost_usd + s.judge_cost_usd for s in ss):.6f}")

    for snippet in sorted({s.snippet for s in scores}):
        print(f"\n  per-issue — {snippet}")
        rows = [s for s in scores if s.snippet == snippet]
        ids = [v.issue_id for v in rows[0].verdicts]
        truth = {v.issue_id: v.severity_truth for v in rows[0].verdicts}
        print(f"    {'issue':<20}{'truth':<11}" + "".join(f"{r.template_name.replace('code_review_',''):<12}" for r in rows))
        for iid in ids:
            line = f"    {iid:<20}{truth[iid]:<11}"
            for r in rows:
                v = next(x for x in r.verdicts if x.issue_id == iid)
                line += f"{('✓ ' + v.severity_given) if v.found else '✗':<12}"
            print(line)
    print(f"\n{'='*78}")


def audit(scores: list[ReviewScore], template: str, snippet: str):
    """
    Print one review in full next to its verdicts.

    Use this whenever a verdict looks wrong. A judge disagreement is only
    informative if you can read what it was judging — otherwise you're guessing
    at whether the judge erred or the output genuinely changed.
    """
    s = next(x for x in scores if x.template_name == template and x.snippet == snippet)
    print(f"\n{'='*78}")
    print(f"AUDIT — {template} on {snippet}")
    print(f"{'='*78}")
    for v in s.verdicts:
        mark = "✓" if v.found else "✗"
        print(f"  {mark} {v.issue_id:<20} truth={v.severity_truth:<10} given={v.severity_given}")
    print(f"\n{'-'*78}\nREVIEW TEXT AS JUDGED:\n{'-'*78}")
    print(s.review_text)
    print(f"{'='*78}")


def save(scores: list[ReviewScore], log_dir: str = "logs"):
    Path(log_dir).mkdir(exist_ok=True)
    with open(Path(log_dir) / "review_scores.jsonl", "a") as f:
        for s in scores:
            f.write(json.dumps(asdict(s)) + "\n")


# ── Entry point ───────────────────────────────────────────────────────────────

TEMPLATES = ["code_review_neutral", "code_review_strict", "code_review_friendly"]


async def main(model: str = "claude", audit_target: tuple[str, str] | None = None):
    snippets = json.load(open("test_sets/code_review.json"))
    scores = []
    for snip in snippets:
        for name in TEMPLATES:
            scores.append(await score_review(name, snip, model=model))
    report(scores)
    save(scores)
    if audit_target:
        audit(scores, *audit_target)


if __name__ == "__main__":
    # Audit the case where the judge disagreed with our manual read: did the
    # friendly persona actually report the None-dereference, or did the judge
    # count a silent fix in the refactor?
    asyncio.run(main(audit_target=("code_review_friendly", "user_lookup")))
