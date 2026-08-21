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

| # | Technique | What it measures |
|---|-----------|------------------|
| 1 | Zero-shot vs. few-shot | Accuracy delta; how many examples before it plateaus |
| 2 | Role / persona prompting | Tone and thoroughness change across personas |
| 3 | JSON / structured output | First-try parse success rate, per model |
| 4 | Tool calling | Correct tool and argument selection |
| 5 | Retry-on-invalid-JSON | Recovery rate within 1–2 retries |
| 6 | Chain-of-thought | Accuracy gain vs. token/cost increase |
| 7 | Self-consistency (N=5) | Majority-vote accuracy vs. single-shot |
| 8 | Prompt chaining | Quality vs. a single mega-prompt |
| 9 | LLM-as-judge | Consistency across repeated judge calls |
| 10 | Regression testing | Does the harness catch a real regression? |

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

| File | Purpose |
|------|---------|
| `prompt_library.py` | Reusable prompt templates + registry |
| `eval_harness.py` | Scoring engine — exact-match + LLM-as-judge |
| `llm_client.py` | API layer carried over from Month 0 |
| `test_sets/` | Labeled test data for each technique |
| `prompt_library.md` | Written analysis of all techniques |
| `logs/` | Eval run logs, JSON-lines (gitignored) |
| `requirements.txt` | Python dependencies |
| `.env.example` | API key template |

---

## Full Analysis

See [prompt_library.md](./prompt_library.md) for the complete write-up — techniques tested, harness results, and recommendations based on real data.

---

## Previous: [Month 0 — AI Landscape Explorer](../m0-landscape/)
## Next: Month 2 — Tool Use & Agents
_(link when built)_
