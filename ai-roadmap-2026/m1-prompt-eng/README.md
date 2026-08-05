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

_(fill in at end of month — 3–5 bullets from your own experiments)_

---

## Cost

_(fill in — roughly what does a full harness run cost?)_

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
