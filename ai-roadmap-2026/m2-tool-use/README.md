# Month 2: Tool Use & Agents
**Part of Rev's AI Engineer Roadmap 2026**

> A job application tracking agent you run from the command line — and actually use. It searches postings, saves the ones worth pursuing, tracks their status, drafts follow-ups, and asks permission before sending anything.

---

## What this does

- **A ReAct loop** — the model calls a tool, the result feeds back into the conversation, the model continues until it has an answer. Multi-turn, with an iteration cap.
- **Seven tools spanning the full risk range**, from a read-only job search to a follow-up email that reaches a real hiring manager.
- **Guardrails proportional to blast radius** — validation everywhere, server-side scoping on your data, idempotency on writes, and a human approval gate on the one action that can't be undone.
- **A trajectory eval harness** that scores not just whether the agent got the right answer but whether it took a sensible path to get there.

---

## The tool set

| Tool | Risk class | Guardrail |
|---|---|---|
| `search_jobs` | read-only, external | validation, rate limit, cache |
| `get_job_details` | read-only, external | validation |
| `list_applications` | scoped read — your data | owner injected server-side |
| `save_application` | low-blast write | idempotency key |
| `update_status` | low-blast write | legal transitions only, audit log |
| `draft_followup` | generative, no side effect | none |
| **`send_followup`** | **high blast** | **human approval gate, never auto-send** |

The spread is deliberate. Guardrails only make sense when tools differ in what they can damage — uniform protection is too strict for a search and too loose for an email.

---

## Setup

```bash
# 1. Clone
git clone https://github.com/revanthbobba1/ai-roadmap-2026
cd ai-roadmap-2026/m2-tool-use

# 2. Virtual environment
python -m venv .venv
source .venv/bin/activate   # Mac/Linux

# 3. Dependencies
pip install -r requirements.txt

# 4. API keys
cp .env.example .env
# Edit .env and add your Anthropic key

# 5. Run
python agent.py "find me backend engineer jobs in Boston"
```

---

## Fixtures vs. live data

Weeks 1–4 run against recorded job postings in `fixtures/`. Week 5 swaps in a live API behind the same interface.

That split exists because live APIs return different data every day, so a trajectory test recorded today fails tomorrow for reasons that have nothing to do with the agent. Fixtures keep the eval reproducible; the live backend is for actually using the thing. Record-and-replay is a real production pattern, not a shortcut.

---

## Experiments

| # | Experiment | What it measures |
|---|---|---|
| 1–3 | Loop mechanics, multi-tool chains, context growth | tokens per turn — the curve, not the total |
| 4–5 | Overlapping tool descriptions; selection vs. argument accuracy | misroute rate before/after rewriting |
| 6–7 | No-tool-needed and should-refuse cases | over-retrieval; does it decline "apply to everything" |
| 8–9 | Server-side scope injection; budgets and caps | can a crafted input reach data outside your own |
| 10–11 | Trajectory vs. outcome scoring; N runs | pass rate and pass^k |
| 12–13 | Stretch: workflow vs. agent; injection via tool result | cost/latency/reliability of a fixed pipeline |

---

## What I learned

_(fill in at end of month — 3–5 bullets from your own experiments)_

---

## Cost

_(fill in — roughly what does a full eval run cost?)_

---

## Files

| File | Purpose |
|------|---------|
| `agent.py` | The ReAct loop |
| `tools/` | One module per tool, plus the registry |
| `schemas.py` | Pydantic models → JSON Schema |
| `guardrails.py` | Risk classes, validation, budgets, approval gate |
| `backend.py` | Fixture store; live API behind the same interface |
| `fixtures/` | Recorded job postings — keeps the eval reproducible |
| `agent_eval.py` | Trajectory + outcome scoring |
| `eval_sets/` | The four eval categories |
| `applications.json` | Your actual tracked applications |
| `agent_design.md` | Written analysis |
| `llm_client.py` | Carried over from Month 1 |
| `logs/` | Traces (gitignored) |

---

## Full Analysis

See [agent_design.md](./agent_design.md) — tool descriptions tried, misroute rates, guardrails by risk class, and eval results.

---

## Previous: [Month 1 — Prompt Engineering](../m1-prompt-eng/)
## Next: Month 3 — RAG
_(where retrieval becomes one more tool in this same agent, not a separate system)_
