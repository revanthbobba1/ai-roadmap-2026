# Prompt Engineering & Evaluation — Month 1 Analysis

**Rev Bobba | AI Engineer Roadmap 2026**

Models tested: `claude-haiku-4-5` (Anthropic), `gpt-4o` (OpenAI)

---

## Section 1: Techniques Tested

| Technique | Definition | Status |
|-----------|------------|--------|
| Zero-shot | Instruction only, no examples | ✅ |
| Few-shot | Instruction + 2–3 worked examples | ✅ |
| Prose rules | Policy stated explicitly in the instruction | ✅ |
| Role / persona | Persona set in the system prompt to shift tone and strictness | ⬜ |
| Structured output | Output constrained to a Pydantic schema | ⬜ |
| Tool calling | Model returns a structured tool call rather than prose JSON | ⬜ |
| Retry-on-invalid | Re-prompt with the validation error when parsing fails | ⬜ |
| Chain-of-thought | Model reasons step by step before answering | ⬜ |
| Self-consistency | N runs at temp > 0, majority vote on the answer | ⬜ |
| Prompt chaining | Task split across sequential prompts | ⬜ |
| LLM-as-judge | Second model scores outputs against a written rubric | ⬜ |

---

## Section 2: Results

### Experiment 1a — Zero-shot vs. few-shot (easy test set)

**Task:** Support ticket routing (BILLING / TECHNICAL / ACCOUNT / OTHER)
**Test set:** `test_sets/ticket_routing.json` — 20 hand-labeled tickets
**Model:** claude-haiku-4-5

| Prompt version | Passed | Mean score | Cost |
|---|---|---|---|
| `ticket_router_zero_shot` | 20/20 | 1.00 | $0.001313 |
| `ticket_router_few_shot` | 20/20 | 1.00 | $0.002129 |

**Observations:**

Perfect tie. Few-shot cost **62% more for zero measurable benefit** — the three
examples are re-sent on every call. At 30K calls/month that's $39 vs $64.

The tie is a finding about the *eval*, not the prompts. Every ticket contained a
giveaway keyword ("invoice", "crash", "password"), so the model never had to
exercise judgment. Both prompts at 100% means this test set has no
**discriminating power** — a third, better prompt would also score 20/20 and
teach nothing. Classic **ceiling effect**.

Correct reading of a ceiling result: *the model already knows this task; no
intervention is warranted.* Not "few-shot doesn't work."

---

### Experiment 1b — Conveying an uninferable policy

Rebuilt the test set to discriminate. Introduced an arbitrary routing policy the
model cannot deduce — both readings of each rule are defensible, the company
picked one:

- **Rule A** — auth issues (password, 2FA, SSO, login) → ACCOUNT, not TECHNICAL
- **Rule B** — any refund request → OTHER for manual approval, not BILLING
- **Rule C** — ticket spanning two categories, or too vague → OTHER

**Test set:** `test_sets/ticket_routing_hard.json` — 24 cases, tagged by hardness
(8 noisy / 8 convention / 8 abstention). Leakage check run: no few-shot example
appears in the test set.

Three templates, identical task, differing only in *how* the policy is conveyed.

| Prompt version | Passed | Mean | Cost | Prompt overhead |
|---|---|---|---|---|
| `hard_zero_shot` (no policy) | 13/24 | 0.54 | $0.001647 | — |
| `hard_zero_shot_rules` (prose) | **24/24** | **1.00** | $0.003017 | +63 tokens |
| `hard_few_shot` (examples) | 18/24 | 0.75 | $0.003459 | +93 tokens |

**Per-hardness breakdown:**

| | abstention | convention | noisy |
|---|---|---|---|
| no policy | 4/8 | 1/8 | 8/8 |
| few-shot | 7/8 | 3/8 | 8/8 |
| prose rules | 8/8 | 8/8 | 8/8 |

**Observations:**

**Few-shot was dominated** — lower score *and* higher cost. No scenario ships it
for this task. A stronger result than a tie.

**Few-shot split hard by rule type.** It transmitted abstention well (4/8 → 7/8)
but barely moved convention (1/8 → 3/8) — despite convention having *two*
demonstrating examples to abstention's one. More coverage, worse result, so
coverage isn't the mechanism.

**The mechanism is prior strength.** The model arrives believing "password reset
is a technical problem" — strongly, and correctly in most contexts. One example
contradicting that doesn't overturn it; the model reads the example as an oddity
rather than a rule. Abstention faces no such prior — the model is genuinely torn
on a mixed ticket, so one example resolves it easily.

> Few-shot's power to change behavior is inversely proportional to the strength
> of the prior it's fighting. One example resolves uncertainty. One example does
> not overturn conviction.

**Why prose won — scope specification.** The rule names four trigger terms and
universally quantifies them ("*Anything* about passwords, two-factor codes, SSO,
or logging in"). The example marks one point and leaves the model to infer
whether SSO is in scope, whether 2FA counts, whether it was a rule or an oddity.

> Prose states the boundary. An example marks one point near it.

*Initial hypothesis, disproved below:* that the phrase `not TECHNICAL` was doing
the work by naming the prior it overrides. Ablation says no — see Experiment 1c.

**No collateral damage.** All three scored 8/8 on noisy. The worry that Rule C
would over-fire and dump vague-but-classifiable tickets into OTHER did not
materialize. Worth having checked rather than assumed — an aggregate score would
have hidden it either way.

**The baseline column is a prior measurement.** This is the reusable technique.
You can't inspect a model's priors, but the no-policy control reads them out:

| baseline | meaning | intervention needed |
|---|---|---|
| below chance (1/8) | confidently wrong — strong prior against you | prose that names the belief |
| near chance (4/8) | genuinely uncertain, no firm prior | examples suffice |
| already correct (8/8) | model knows this | none — intervention is pure cost |

Random across four categories is ~2/8. Scoring *below* chance means systematic
wrongness, not confusion.

---

### Experiment 1c — Ablation: does naming the prior matter?

**Ablation** = removing one component from a working system to measure its
contribution. Here: delete `not TECHNICAL` and `not BILLING` from the prose
rules, change nothing else (−9 tokens), rerun.

**Hypothesis under test:** prose won because it named the belief it was
overriding, not merely because it stated the rule.

| Prompt version | Passed | convention | Cost |
|---|---|---|---|
| `hard_zero_shot_rules` (full) | 24/24 | 8/8 | $0.003017 |
| `hard_zero_shot_rules_ablated` | **24/24** | **8/8** | $0.002863 |

**Result: hypothesis disproved.** Identical scores. Naming the prior contributed
nothing measurable. The original explanation was over-fitted to one result —
attributing the win to the most interesting-sounding feature of the prompt
rather than the one actually responsible.

**Revised mechanism — scope specification.** Prose enumerates four trigger terms
under a universal quantifier ("*Anything* about..."). The few-shot example gives
one instance and leaves generalization to the model: is SSO in scope? Is 2FA? Is
this a rule or an oddity? Prose states the boundary; an example marks one point
near it.

**Caveat, and it's load-bearing:** these rules are simple and cleanly stateable.
Where a rule resists articulation — tone, voice, output formatting — there may
be no compact prose that specifies the boundary, and examples should win.
Untested here.

**Shipping decision:** the ablated version. Same accuracy, 9 fewer tokens, less
to maintain. When two prompts tie, the simpler one wins by default.

**Open question — does naming the prior help against a *harder* prior?**

Proposed after the ablation: naming may still contribute when the model's belief
is strong enough that a plain rule statement can't shift it.

Evidence against, from this run: the prior here already *was* strong. Baseline
convention was 1/8 against a ~2/8 random floor — below chance, meaning the model
was systematically wrong rather than uncertain. Plain prose overturned it fully.

But this cannot be settled here, for the same reason the first experiment
couldn't: **both prose variants hit 8/8 — another ceiling effect.** "No
difference detected" is not "no difference exists" when neither prompt can score
higher.

A test would need a rule where plain prose *fails*, then check whether negation
rescues it. Requires a prior far harder than a plausible-either-way routing
convention — e.g. a rule contradicting near-universal knowledge, or one using a
common word in a non-standard sense ("urgent means low priority here").

**Method note.** The value of this experiment was that it was designed to break
a conclusion already written down, and did. One ablation cost under a cent and
corrected an explanation that would otherwise have been carried into Month 2 as
settled fact.

---

### Experiment 1d — Cross-model replication (GPT-4o)

Every result above came from one model, making them `claude-haiku-4-5` facts
rather than general ones. Reran the identical suite on `gpt-4o`.

| Template | Claude | GPT-4o | Claude cost | GPT-4o cost |
|---|---|---|---|---|
| `hard_zero_shot` | 13/24 | 12/24 | $0.001647 | $0.004285 |
| `hard_zero_shot_rules` | 24/24 | 24/24 | $0.003017 | $0.007825 |
| `hard_zero_shot_rules_ablated` | 24/24 | 24/24 | $0.002863 | $0.007285 |
| `hard_few_shot` | 18/24 | 21/24 | $0.003459 | $0.009505 |

**Convention breakdown — the diagnostic column:**

| | Claude | GPT-4o |
|---|---|---|
| no policy | 1/8 | **0/8** |
| few-shot | 3/8 | 5/8 |
| prose | 8/8 | 8/8 |
| prose ablated | 8/8 | 8/8 |

**The prior is shared, not model-specific.** GPT-4o scored 0/8 with no policy —
against a ~2/8 random floor, that means it routed *every* auth ticket to
TECHNICAL and *every* refund to BILLING without exception. Both models learned
this convention independently. The test set measures a real property of how
these models were trained, not a quirk of one.

**Ordering replicates exactly:** prose > few-shot > no policy, on both models.
The ablation null result replicates too — naming the prior adds nothing on
either. Two independent confirmations rather than one.

**One real difference — few-shot is model-sensitive in magnitude.** GPT-4o was
more responsive to demonstrations (21/24 vs 18/24; convention 5/8 vs 3/8). The
ranking held, the gap narrowed. Practical consequence: a prompt tuned on one
model may not transfer at the same strength, which is what `PromptTemplate.
tuned_for` exists to record.

**Cost:** GPT-4o ran ~2.6× more expensive across every template — consistent
with the Month 0 pricing finding.

---

### Experiment 2 — Role / persona prompting

**Task:**
**Personas tested:**

**Observations:**
_(fill in)_

---

### Experiment 3 — Structured output extraction

**Schema:**
**First-try parse rate — Claude:** ___% **GPT-4o:** ___%

**Observations:**
_(fill in)_

---

### Experiment 4 — Tool calling

**Tool schema:**
**Correct tool selected:** Claude ___/___ · GPT-4o ___/___

**Observations:**
_(fill in)_

---

### Experiment 5 — Retry-on-invalid-JSON

**Recovery rate within 1 retry:**
**Within 2 retries:**

**Observations:**
_(fill in)_

---

### Experiment 6 — Chain-of-thought

**Task:**

| Version | Accuracy | Tokens out | Cost |
|---|---|---|---|
| Direct answer | | | |
| CoT | | | |

**Observations:**
_(fill in)_

---

### Experiment 7 — Self-consistency (N=5)

| Version | Accuracy | Cost multiplier |
|---|---|---|
| Single-shot | | 1× |
| Majority vote (N=5) | | 5× |

**Observations:**
_(fill in — was the accuracy gain worth 5× the cost?)_

---

### Experiment 8 — Prompt chaining vs. single mega-prompt

**Task:**

**Observations:**
_(fill in — what failure modes was each approach prone to?)_

---

### Experiment 9 — LLM-as-judge

**Rubric used:**

**Consistency:** ran the same judge call ___ times on identical input; scores varied by ___

**Biases observed:**
- Position bias:
- Verbosity bias:
- Leniency bias:

**Observations:**
_(fill in)_

---

### Experiment 10 — Regression test across prompt versions

**Scoreboard:**

| Version | Passed | Mean score |
|---|---|---|
| v1 | | |
| v2 | | |
| v3 | | |

**Did the harness catch a real regression?**
_(fill in)_

---

## Section 3: When to Use Each Technique

_(fill in — your own recommendations, based on the harness data rather than articles)_

| Technique | Use when | Skip when |
|---|---|---|
| Few-shot | | |
| Role prompting | | |
| CoT | | |
| Self-consistency | | |
| Prompt chaining | | |

---

## Section 4: Eval Harness Design

**What it scores:**

**Why these metrics:**

**Known blind spots:**
_(what can this harness not catch? Every eval has gaps — naming them is the point.)_

---

## Conclusions

_(fill in at end of month)_
