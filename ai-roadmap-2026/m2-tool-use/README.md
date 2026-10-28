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

How the pieces fit. Each layer only knows about the one below it.

```
          ┌─────────── the agent loop ────────────┐
          │  agent.py            hand-built       │
          │  langgraph_agent.py  LangGraph port   │
          └───────────────────┬───────────────────┘
                              │ execute_tool()
                     ┌────────▼────────┐
                     │  guardrails.py  │  budget → rules → idempotency → approval
                     └────────┬────────┘
                     ┌────────▼────────┐
                     │ tools/registry  │  name + description + schema + fn
                     │ tools/*.py      │  the seven tools
                     └────────┬────────┘
                     ┌────────▼────────┐
                     │   backend.py    │  FixtureBackend / LiveBackend
                     └────────┬────────┘
                   fixtures/jobs.json, applications.json

  schemas.py ──> used by every layer above (the shared type definitions)
```

**Runtime**

| File | Purpose |
|------|---------|
| `agent.py` | The ReAct loop and `execute_tool`. The heart of the project. |
| `langgraph_agent.py` | The same agent on LangGraph, wrapped so guardrails survive the port. |
| `guardrails.py` | `Session`, `Budget`, risk classes, legal-transition rules, idempotency, approval gate. |
| `schemas.py` | Pydantic models. Do double duty: generate the JSON Schema the model sees *and* validate what it sends back, so the two can't drift. |
| `backend.py` | Data access. `FixtureBackend` for reproducible evals, `LiveBackend` for real use. |
| `tools/registry.py` | The `Tool` dataclass, the `REGISTRY` dict, and the Anthropic/OpenAI wire formats. |
| `tools/search.py`, `job_details.py`, `applications.py`, `writes.py` | The seven tools, grouped read vs. write. |

**Evaluation** — two suites, because they answer different questions at very different costs.

| File | Purpose |
|------|---------|
| `routing_eval.py` | Tool *choice* only: one API call per case, nothing executed. Cheap enough to re-run on every description tweak. |
| `agent_eval.py` | Full multi-turn runs, N times each, scoring trajectory + outcome + failure attribution. ~30× the cost — a pre-commit gate, not an inner-loop check. |
| `descriptions.py` | The 2×2 description variants (overlapping vs. separable × real names vs. `tool_a/b/c`). Used only by `routing_eval`. |
| `eval_sets/*.json` | The test cases, as data rather than code. |

**Reference and carryover**

| File | Purpose |
|------|---------|
| `one_turn.py` | A teaching script: one round trip with every step printed. Imported by nothing — `agent.py` is this in a loop. Kept as something to re-read before an interview. |
| `llm_client.py` | Month 1's API wrapper. The agent talks to the SDK directly, so the only thing still used here is `calculate_cost`. |
| `agent_design.md` | The written analysis. |
| `fixtures/`, `applications.json`, `logs/` | Recorded postings; your real tracked applications; traces. The last two are gitignored. |

---

## Full Analysis

See [agent_design.md](./agent_design.md) — tool descriptions tried, misroute rates, guardrails by risk class, and eval results.

---

## Previous: [Month 1 — Prompt Engineering](../m1-prompt-eng/)
## Next: Month 3 — RAG
_(where retrieval becomes one more tool in this same agent, not a separate system)_
