# AI Engineer Roadmap 2026
**Rev Bobba** — Java SWE → AI/LLM Engineer

> Three projects, built rather than read about. Each one ships with an eval
> suite and a written analysis of what the experiments actually showed —
> including the ones that produced no result, and why.

---

## Projects

| | Project | What it is | Status |
|---|---|---|---|
| **0** | [m0-landscape](./m0-landscape/) | API explorer, Claude vs. GPT-4o comparison | ✅ Complete |
| **1** | [m1-prompt-eng](./m1-prompt-eng/) | Prompt library + eval harness with a regression gate. 11 experiments. | ✅ Complete |
| **2** | [m2-tool-use](./m2-tool-use/) | Job application tracking agent — 7 tools, guardrails by blast radius, trajectory eval. Hand-built ReAct loop, then ported to LangGraph, then rebuilt as a fixed pipeline for comparison. | ✅ Complete |
| **3** | m3-rag | RAG, ending in a deployment | ⬜ Next |

**The plan changed in October.** It started as six months — separate months for
agents, deployment and a capstone. Month 2 turned out to absorb roughly 80% of
the agents month once it had a ReAct loop, short-term memory and a tool
registry, so they were merged. Deployment became one deliverable at the end of
Month 3 instead of a month of its own, and the capstone became these three
projects written up properly.

Three projects someone can discuss in depth beats six rushed ones, because an
interviewer picks one and probes until you run out of answers.

---

## A few findings

Short versions. Each project's README and analysis doc has the numbers.

- **A prompting technique that wins on an easy test set has told you nothing.**
  Nine ceiling effects across the two projects — eval sets where every variant
  maxed the metric, so the metric had stopped measuring. An eval that cannot
  produce a losing score cannot produce information.
- **Tool descriptions were not load-bearing here, and that is a scoping result
  rather than a general one.** 18/18 on every variant of a 2×2. The queries
  carried the routing signal, and three functionally distinct tools left nothing
  to disambiguate.
- **Guardrails should be tiered because human attention is the scarce
  resource.** A gate on every tool means a human reviews everything, which is a
  slow autocomplete. Blast-radius classes are what make the gate affordable on
  the one action that is irreversible.
- **A framework does not carry your safety layer with it.** Porting the agent to
  LangGraph silently bypassed every guardrail, zeroed the cost metric, and
  stripped `extra="forbid"` from the tool schemas on the wire. Nothing failed a
  test — the tools still worked.
- **A green eval suite does not mean the tests are real.** Four of twelve agent
  eval cases were asserting nothing. They surfaced only because an
  implementation that physically cannot do the task passed them too.

---

## Stack

Actually used: **Claude** (Anthropic) and **GPT-4o** (OpenAI) via their SDKs,
**Python**, **Pydantic** for schemas that both generate tool specs and validate
what comes back, **LangGraph** / **langchain-anthropic** for the Month 2 port.

Not yet: deployment (Month 3), and any vector store or retrieval library — those
arrive with RAG.

---

## Running anything here

Each project is self-contained with its own `requirements.txt` and
`.env.example`. From a project directory:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # add your API key
```

Evals cost real money, so each project's README lists what a full run costs.
Nothing here is more than a dollar.
