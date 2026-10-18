# Agent Design — Month 2 Analysis

**Rev Bobba | AI Engineer Roadmap 2026**

A job application tracking agent: ReAct loop, seven tools spanning the full risk
range, guardrails proportional to blast radius, trajectory evaluation.

Model: `claude-haiku-4-5`. All runs at `temperature=0.0` unless stated.

---

## Section 1: The Tool Set

| Tool | Risk class | Guardrail |
|---|---|---|
| `search_jobs` | read-only, external | validation, rate limit, cache |
| `get_job_details` | read-only, external | validation |
| `list_applications` | scoped read — user's data | owner injected server-side |
| `save_application` | low-blast write | idempotency key |
| `update_status` | low-blast write | legal transitions only, audit log |
| `draft_followup` | generative, no side effect | none |
| `send_followup` | **high blast** | human approval gate, never auto-send |

The spread is the point. A bad search costs a fraction of a cent; a bad
follow-up email reaches a hiring manager and cannot be recalled. Uniform
guardrails would be too strict for the first and too loose for the last.

---

## Section 2: Results

### Experiment 1 — The ReAct loop

**Built:** `one_turn.py` (the round trip, with every step printed) then
`agent.py` (the same thing in a loop, with an iteration cap and a trace).

**The loop:** model emits a tool call → you execute it → the result goes back as
a `tool_result` → the model runs again → repeat until it returns text instead of
a call. Reasoning and acting interleave in one conversation, which is what makes
multi-step questions answerable.

**Verified chaining.** Asked *"which Boston job pays best, and what does it
require?"*, the agent:

1. called `search_jobs(location="Boston")` — 4 results with salary ranges
2. compared them, picked the highest (`j_004`, $175–225k)
3. called `get_job_details(job_id="j_004")` for requirements
4. answered both halves

Step 3 was not knowable from the question. The chain is real, not two
independent calls.

**Context growth — the measurement that matters:**

| turn | tool | input tokens | growth |
|---|---|---|---|
| 0 | `search_jobs` | 1244 | — |
| 1 | `get_job_details` | 1489 | +245 |
| 2 | (answered) | 1688 | +199 |

Total billed input: **4,421 tokens across 3 calls**.

Each tool call adds ~220 tokens permanently, and every turn re-pays for the
whole conversation. So the cost of a run is **quadratic in turns, not linear**:

| turns | last turn input | total billed | vs 3 turns |
|---|---|---|---|
| 3 | 1,684 | 4,392 | 1.0× |
| 5 | 2,124 | 8,420 | 1.9× |
| 8 | 2,784 | 16,112 | 3.7× |
| 12 | 3,664 | 29,448 | **6.7×** |

Three practical consequences:

- **Iteration caps are cost control**, not just a stuck-detector. 4× the turns
  costs 6.7× the input.
- **Terse tool results are worth real money.** `search_jobs` returns one line
  per job rather than full records; returning all 8 descriptions would push
  ~220/turn to ~2000/turn.
- **Step efficiency is a financial metric.** An agent taking 6 turns where 3
  would do is roughly 3× the spend, not slightly worse.

---

### Experiment 2 — Routing, and what actually carries the signal

**Question:** how much does tool description quality affect tool selection?

**Design:** a 2×2 — descriptions (`overlapping` / `separable`) crossed with tool
names (`descriptive` / `neutralised to tool_a/b/c`). 18 cases across four
categories: single-tool, ambiguous, multi-tool, and no-tool-needed.

| variant | selection | args | over-retrieval |
|---|---|---|---|
| overlapping | 18/18 | 5/5 | 0/4 |
| separable | 18/18 | 5/5 | 0/4 |
| neutral_overlapping | **17/18** | 5/5 | 0/4 |
| neutral_separable | 18/18 | 5/5 | 0/4 |

**Result: no detectable difference.** 17/18 vs 18/18 at n=18 gives 95% intervals
of [84%, 100%] and [77%, 100%] — overlapping almost entirely. One case is not a
finding at this sample size.

**The first run was a design error.** Only descriptions were varied while tool
*names* stayed fully informative:

```
name:        list_applications
description: "Look up job records for the user."
```

The model never needed the description. The weaker signal was varied and the
stronger one left intact. Hence the neutral-name variants.

**The real diagnosis: the routing signal is in the queries.**

| query | signal |
|---|---|
| "Tell me more about job **j_002**" | an id — only one tool takes one |
| "Show me **my saved** jobs" | possessive — only one tool reads user data |
| "**Find me** backend jobs **in Boston**" | search verb plus a location |

With three functionally distinct tools, the user's phrasing was nearly
unambiguous regardless of names or descriptions. There was never much for the
metadata to disambiguate.

> **Tool description quality is a scoping question, not a universal practice.**
> With few, functionally distinct tools and clearly-phrased queries, neither
> names nor descriptions were load-bearing. Description tuning should matter
> when the tool set is large, when functions genuinely overlap, or when queries
> are vague — none of which were true here.

Testable once Week 3 takes the set to seven tools: if `save_application` and
`update_status` start getting confused, the conditions this experiment lacked
will exist, and the eval set is already written.

**The one failure is qualitatively interesting.** `r12` — *"Get me information
on the Corvid Labs role"* — under `neutral_overlapping` the agent called **no
tool at all** rather than guessing. Faced with three indistinguishable options
and no `job_id` available, it abstained and answered directly. Arguably correct
behaviour, scored as a miss. Abstention appearing unprompted, same pattern as
Month 1.

**Over-retrieval was 0/4 everywhere** — the agent never called a tool for
"what makes a good cover letter opening?" But all four no-tool questions are
generic advice no tool plausibly covers, so this metric had no room to move.
A ceiling, not a result.

---

### Experiment 3 — Guardrails by blast radius

_(Week 3)_

---

### Experiment 4 — Trajectory evaluation

_(Week 4)_

---

## Bugs and corrections worth recording

Three things broke in ways that were more instructive than a clean run.

**1. The SDK changed underneath the project.** `anthropic` 1.0 (2026-08-20)
removed `temperature`, `top_p` and `top_k` from `messages.create()`. Month 1's
venv pinned an older release so `llm_client.py` worked all month; a fresh
install resolved 1.x and the same call raised `TypeError`. The API still accepts
the parameters — `extra_body={"temperature": 0.0}` is the documented path.

Concrete version of a principle that is usually abstract: a dependency changed
and silently broke working code. Month 1's `regression.py` could not have caught
it, because the failure is in the harness rather than in a prompt.

**2. A required argument the caller could not sensibly fill.** `SearchJobsArgs.
query` was required. Asked *"which Boston job pays best?"* — a question naming no
role — the model had to supply something and sent `query="job"`, which matched
nothing, because the word "job" appears nowhere in a job description. Right tool,
wrong argument, and the schema left no good option.

> A required field the caller cannot always fill is a schema bug, not a model
> bug.

Fixed by making `query` optional and saying in the field description what
omitting it means.

**3. A guardrail fighting its own schema.** `apply_guardrails` injected `owner`
into the arguments dict, which was then re-validated against a model with
`extra="forbid"` and no `owner` field. The injection was in the wrong channel.

Server-side parameters belong on the **session**, not the arguments: the session
is trusted state, the arguments are model-supplied, and keeping them separate is
the entire point. A tool reads `ctx.owner`, and there is no path by which the
model could have influenced it.

---

## Section 3: When to Use What

_(Week 5)_

## Section 4: Eval Design and Known Blind Spots

_(Week 5)_

## Section 5: When You Would NOT Build an Agent

_(Week 6 — the workflow comparison)_
