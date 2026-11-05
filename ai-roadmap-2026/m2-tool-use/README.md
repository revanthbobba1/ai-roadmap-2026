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

## The loop

Nothing executes because the model asked for it. Every proposed call passes four
gates first, and three of them can return a string to the model instead of
running anything.

```mermaid
flowchart TD
    Q([user question]) --> M

    M["<b>model turn</b><br/>system prompt + full history + tool specs"]
    M --> D{"stop_reason?"}

    D -->|end_turn| ANS([final answer])
    D -->|tool_use| CAP

    CAP{"turn &lt; max_iterations?"}
    CAP -->|no| STUCK([IterationCapExceeded<br/><i>cap-hit rate = health metric</i>])
    CAP -->|yes| V

    subgraph EX["execute_tool — nothing runs until all four pass"]
        direction TB
        V["<b>1. schema validation</b><br/>types, ranges, extra=forbid"]
        B["<b>2. budget</b><br/>calls, spend, high-blast count"]
        R["<b>3. business rules</b><br/>e.g. legal status transitions"]
        I["<b>4a. idempotency</b><br/>writes only — server-side key"]
        A["<b>4b. approval gate</b><br/>HIGH_BLAST only — human says yes"]
        RUN["tool runs<br/><i>session passed as ctx, never as args</i>"]

        V --> B --> R --> I --> A --> RUN
    end

    V -.->|invalid| ERR
    B -.->|over budget| ERR
    R -.->|illegal| ERR
    A -.->|denied| ERR

    ERR["REFUSED / ERROR string"]

    RUN --> RES["tool_result appended<br/><i>context grows every turn</i>"]
    ERR --> RES
    RES --> M

    classDef gate fill:#fff4e6,stroke:#d9822b,color:#000
    classDef danger fill:#ffe6e6,stroke:#c0392b,color:#000
    classDef done fill:#e8f5e9,stroke:#2e7d32,color:#000
    class V,B,R,I gate
    class A,ERR,STUCK danger
    class ANS done
```

Three ways out: an answer, a refusal fed back for the model to correct, or the
iteration cap. The cap-hit rate is the single best early warning in production —
an agent that hits it is an agent that got stuck.

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

**Tool descriptions mattered far less than expected — and the test set is why.**
A 2×2 of overlapping vs. separable descriptions, crossed with real vs.
neutralised tool names, scored 18/18, 18/18, 17/18, 18/18. No detectable
difference at that sample size. Two causes: the queries carried the routing
signal themselves (an id, a possessive "my", a search verb plus a location), and
there were only three functionally distinct tools, so there was nothing to
disambiguate. The conclusion is not "descriptions don't matter" — it is that
description tuning is a scoping question. It should matter with a large tool
set, genuinely overlapping functions, or vague queries, and I had none of those.

**Over-retrieval is the half of tool use that usually goes untested.** It is
tempting to let an application reach for a tool wherever one might apply, but
every unnecessary call costs latency and money for an answer the model already
had. Measured directly: the fixed pipeline made 4 tool calls on every advice
question — cover letter openings, follow-up timing — where the agent made zero.
Testing only the happy path, that waste is invisible.

The lever is not "prompt the model to call fewer tools." In increasing order of
reliability: scope the tool out in its description (a hint it can ignore), put a
deterministic pre-filter in front so the question never reaches the model, or
don't give it the tool at all. Which one depends on the traffic mix.

**Guardrails should be tiered because human attention is the scarce resource.**
An approval gate on every tool means a human reviews everything, which is a slow
autocomplete rather than an agent. No gate means eventually sending something
irreversible by accident. Classifying tools by blast radius — read-only, scoped
read, reversible write, irreversible — is what makes the gate affordable enough
to keep on the one action that needs it. The human is not removed; they are
removed from six tools so they are available for the seventh.

**A workflow beats an agent whenever the task permits one.** 25% pass vs. 100%,
but 55% cheaper, 35% faster, and with zero run-to-run variance. The finding I
did not expect: all three should-refuse cases passed because the pipeline has no
code path to `send_followup`. In a workflow, blast radius is a design-time
property; in an agent it is a runtime one. The safest agent is the one that was
not built.

**A green eval suite does not mean the tests are real.** Four of twelve cases
were asserting nothing — empty expected-content lists, or a keyword that any
plausible answer contains. They only surfaced because an implementation that
physically cannot save or read the tracker passed them anyway. Running something
known to be broken through the suite is the only way to check the suite works,
and no amount of staring at a 100% tells you.

---

## Cost

All on `claude-haiku-4-5`, temperature 0.

| What | Cost |
|---|---|
| One agent question (2 tool calls) | ~$0.002 |
| One workflow question (4 tool calls, 2 LLM calls) | ~$0.002 |
| `agent_eval.py 5` — 12 cases x 5 runs, hand-built | $0.24 |
| same, LangGraph | $0.22 |
| same, workflow | $0.11 |

So the full three-way comparison is about **$0.57** and ten minutes. Cheap enough
to re-run on every meaningful change, which is the only reason it gets re-run at
all — a suite expensive enough to skip catches nothing.

Two notes on reading those numbers:

- **LangGraph is cheaper by accident.** Its schema conversion strips
  auto-generated `title` fields from the tool definitions, which ship with every
  request. 12% smaller definitions, ~9% lower total. Not a framework
  optimisation, a side effect.
- **The workflow's saving is regime-dependent.** It makes fewer LLM calls (2 vs
  3) but more tool calls (4 vs 2). It looks cheap because these tools are local
  fixture reads. Against a paid API the two extra calls would swamp the model
  call saved.

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
