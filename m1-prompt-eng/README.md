# Month 1: Prompt Engineering & Evaluation
**Part of Rev's AI Engineer Roadmap 2026**

> A reusable prompt library and an automated eval harness that scores prompt variants against a labeled test set — so "this prompt is better" becomes a number instead of a vibe.

---

## What this does

- **`prompt_library.py`** — parameterized `PromptTemplate` class supporting zero-shot, few-shot, role/persona, and chain-of-thought prompting. One place to define, version, and reuse prompts.
- **`eval_harness.py`** — runs any template against a labeled test set and scores outputs automatically. Exact-match for objective tasks; LLM-as-judge with a written rubric for subjective ones.
- **`llm_client.py`** — the API layer carried over from Month 0: async Claude + GPT-4o calls, exponential backoff retry, cost and token tracking.
- Compares prompt versions side by side and prints a scoreboard — the prompt-engineering equivalent of a unit test suite.

---

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/revanthbobba1/ai-roadmap-2026
cd ai-roadmap-2026/m1-prompt-eng

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up API keys
cp .env.example .env
# Edit .env and paste your Anthropic and OpenAI API keys

# 5. Run the prompt library smoke test
python prompt_library.py

# 6. Run the eval harness (compares zero-shot vs. few-shot)
python eval_harness.py
```

---

## Techniques tested

Ten techniques across 11 experiments. Results and full reasoning in
[prompt_library.md](./prompt_library.md).

| # | Technique | What it measures |
|---|-----------|------------------|
| 1 | Zero-shot vs. few-shot | Accuracy delta — plus an ablation and a cross-model replication |
| 2 | Role / persona prompting | Tone and thoroughness change across personas |
| 3 | JSON / structured output | First-try parse success rate, per model, flat schema and hard schema |
| 4 | Tool calling | Whether format compliance can be instructed or has to be enforced |
| 5 | Retry-on-invalid | Recovery rate, and whether the work should have been delegated at all |
| 6 | Chain-of-thought | Accuracy gain vs. token and cost increase |
| 7 | Self-consistency (N=5) | Majority-vote accuracy vs. single-shot, on maths and on extraction |
| 8 | Prompt chaining | Quality vs. one larger prompt |
| 9 | LLM-as-judge | Consistency across repeated judge calls |
| 10 | Regression testing | Does the harness catch a real regression? |

**The headline:** every head-to-head was won by the simpler option — prose rules
over few-shot, computing a value in Python over retrying until the model got it
right, a four-line rubric over a two-stage pipeline, reading a sample-agreement
number over majority voting.

That is a result about *these* tasks: short inputs, flat schemas, four-way
classification, ten-line code snippets. Each elaborate technique exists because
it solves something that appears at greater complexity, and none of those
conditions held here — which is why they lost. The conclusion is not that
sophisticated techniques are overrated, but that reaching for one before
identifying the failure means paying for machinery that addresses a problem you
don't have.

---

## What I learned

- **The basic approach beat the sophisticated one in every head-to-head I ran.**
  There are a lot of well-researched, widely-used techniques for improving model
  output — few-shot, chain-of-thought, self-consistency, prompt chaining. In my
  experiments the plainer option won each time: prose rules beat few-shot,
  computing a value in Python beat retrying until the model got it right, a
  four-line rubric beat a two-stage pipeline. That's counterintuitive, and it's
  the opposite of the instinct to reach for the more advanced tool.

- **The lesson isn't "simple is better" — it's account for the problem space
  before designing for it.** Each technique exists because it solves a real
  failure, and they lost here because my tasks didn't have those failures.
  Over-engineering costs real money and doesn't necessarily solve the problem
  any better. Diagnosing what actually broke is the skill; the techniques are
  the easy part.

- **When to use few-shot:** when the answer has to follow a very specific form
  that can't easily be described — a voice, a format, something you'd struggle
  to write down as a rule. Otherwise state it in prose, which covers a wider
  boundary and captures the edge cases. Few-shot pins down specific data points;
  prose describes the shape of the whole space.

- **Some behaviours can't be prompted away.** An explicit instruction banning
  markdown code fences produced 48 fenced responses out of 48, across two
  providers. Switching to tool calling produced zero. Where a behaviour is
  trained rather than instructed, you need a mechanism that makes the
  alternative impossible, not a firmer request.

- **Validation isn't correctness.** A schema tells you output is well-formed. It
  can't tell you it's right — a model returning a valid-but-wrong enum value
  passes every structural check. Only ground truth catches that, and you need
  both layers.

- **What I'd do differently:** go wider before going deep. I didn't realise how
  many techniques there were, or how many distinct drawbacks each one carries.
  Covering more of them shallowly first would have given me a map of where the
  limitations are — and patterns in those gaps would then have told me which
  ones were actually worth digging into.

---

## Cost

**Roughly $0.75–1.00 for the entire month** — every experiment, every rerun,
both providers.

Logged calls come to $0.2778 across 702 requests, a mean of **$0.0004 per call**.
Several scripts don't route through the shared logger, so the true total is
higher, but the order of magnitude holds: this is under a dollar of experiments.

| model | logged calls | logged cost |
|---|---|---|
| claude-haiku-4-5 | 572 | $0.2149 |
| gpt-4o | 130 | $0.0629 |

GPT-4o ran ~2.3–2.6× the cost of Claude for identical tasks, consistently across
every comparison.

A full `regression.py` run is ~208 calls, well under $0.20 — cheap enough to run
on every change, which is the point. A suite expensive enough to skip catches
nothing.

---

## Files

**Core**

| File | Purpose |
|------|---------|
| `prompt_library.py` | 17 templates across 5 task types. `PromptTemplate` defaults to `temperature=0.0`, not the API's default — reproducibility over variety. |
| `eval_harness.py` | Six scorers, plus a format classifier (bare / fenced / prose) and a guard that aborts a run on any API error. |
| `schemas.py` | Pydantic models, including a strict variant and one with cross-field validation. |
| `llm_client.py` | API layer carried over from Month 0 — async Claude + GPT-4o, backoff, cost tracking. |

**One file per technique**

| File | Technique |
|------|-----------|
| `tool_calling.py` | Tool calling as a format mechanism, not a capability |
| `retry_loop.py` | Bounded retry on invalid output |
| `self_consistency.py` | Majority vote over N samples |
| `self_consistency_extraction.py` | The same, on extraction rather than maths |
| `chaining.py` | Prompt chaining vs. one larger prompt |
| `checklist_scorer.py` | Grounded LLM-as-judge — one binary question per known defect |
| `run_review.py` | Code review task driver |
| `regression.py` | 12 experiment configs scored against `baselines.json`; exits 1 on regression |

**Data and analysis**

| File | Purpose |
|------|---------|
| `test_sets/` | Labelled test data — including `_hard` variants written after the originals turned out to be too easy |
| `baselines.json` | Saved scores the regression gate compares against |
| `prompt_library.md` | The full write-up, ~1,300 lines, all 11 experiments |
| `logs/` | Eval run logs, JSON-lines (gitignored) |
| `requirements.txt`, `.env.example` | Dependencies, API key template |

---

## Full Analysis

See [prompt_library.md](./prompt_library.md) for the complete write-up — techniques tested, harness results, and recommendations based on real data.

---

## Previous: [Month 0 — AI Landscape Explorer](../m0-landscape/)
## Next: [Month 2 — Tool Use & Agents](../m2-tool-use/)
