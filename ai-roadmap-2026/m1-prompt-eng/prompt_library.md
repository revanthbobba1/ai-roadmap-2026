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

**Task:** Python code review. Two snippets, 5 planted defects each, severity
spread from `critical` to `trivial`.
**Templates:** identical user prompt, differing only in system prompt.

- `code_review_neutral` — no role (control)
- `code_review_strict` — senior staff engineer, pre-merge, flag every defect
- `code_review_friendly` — warm mentor, lead with positives, keep them motivated

Output is prose, so `exact_match` cannot score it. Built `checklist_scorer.py`
(see Experiment 2b) instead.

**Results (temperature 0.0, claude-haiku-4-5):**

| Template | recall | critical recall | severity agreement | tokens out |
|---|---|---|---|---|
| `code_review_neutral` | 80% | 50% | 80% | 618 |
| `code_review_strict` | **100%** | **100%** | 70% | 798 |
| `code_review_friendly` | 60% | 50% | 67% | 531 |

**Per-issue:**

| issue | truth | neutral | strict | friendly |
|---|---|---|---|---|
| sql_injection | critical | ✓ critical | ✓ critical | ✓ critical |
| bare_except | high | ✓ critical | ✓ high | ✓ medium |
| mutable_default | high | ✓ high | ✓ high | ✓ medium |
| none_deref | medium | ✓ high | ✓ medium | ✗ |
| unused_import | trivial | ✓ trivial | ✓ trivial | ✗ |
| no_validation | high | ✗ | ✓ high | ✗ |
| float_money | high | ✗ | ✓ medium | ✗ |
| print_side_effect | medium | ✓ medium | ✓ high | ✓ medium |
| range_len | trivial | ✓ trivial | ✓ trivial | ✓ trivial |
| naming | trivial | ✓ trivial | ✓ medium | ✓ trivial |

**Observations:**

**Persona changes capability, not just tone.** The initial prediction — and the
intuitive one — was that a persona shifts delivery while detection stays
constant. False. Strict caught every planted defect; friendly missed four,
including two `high`-severity bugs in `discount_calc` that would ship a money
error (`no_validation` allows a discount over 100%, producing a negative total).

**Friendly systematically under-rates severity.** Both `high` issues in
`user_lookup` came back as medium. The instruction to keep the developer
"feeling motivated" leaked from tone into risk assessment. Behind a
severity-keyed merge gate, this persona ships defects the strict one blocks.

**Friendly also fixed a bug it never reported.** Its refactor contains
`if row:`, silently patching `none_deref` without ever describing it. For a
persona whose stated purpose is mentoring, that's the worst outcome: the bug is
gone and the developer learned nothing.

**Cost favours strict.** 798 vs 531 output tokens — 50% more — for +40 points of
recall and +50 of critical recall.

**Strict's weakness is severity inflation** (70% agreement, lowest of the
three): `naming` trivial→medium, `print_side_effect` medium→high. A reviewer who
escalates everything conveys as little as one who escalates nothing. It also
*under*-rated `float_money` (high→medium), so the inflation isn't uniform.

---

### Experiment 2a — Temperature as a confound (a retracted conclusion)

The first run of this experiment was at the API default `temperature=0.7`.
It produced:

| | critical recall (temp 0.7) | critical recall (temp 0.0) |
|---|---|---|
| neutral | 75% | 50% |
| strict | 75% | **100%** |
| friendly | 75% | 50% |

At 0.7 all three looked identical and the conclusion drawn was *"persona affects
total recall but has no effect on the issues that matter."* At temperature 0 the
personas differ by 50 points on exactly that metric.

**Attribution caveat — three things changed between these runs**, not one:
temperature 0.7→0.0, a severity rubric added to judge Question 2, and judge
Question 1 tightened to reject silent fixes. Attributing the CRIT change to
temperature alone is not demonstrated. What the evidence does support:

- The rubric cannot move CRIT directly. `critical_recall` is computed from
  `v.found` only; the rubric shapes the severity answer, not the found answer.
- The Question 1 tightening *can* lower `found`, and plausibly explains neutral
  and friendly dropping 75%→50%.
- It cannot explain strict rising 75%→100%. A harsher judge cannot make a review
  find more defects. Something changed review-side, and temperature was the only
  review-side change.

So temperature is *implicated but not isolated.* A clean ablation would rerun at
0.7 with the current judge. Not done.

**The methodological error, twice in one day:** changing several variables at
once and then attributing the result to the most interesting-looking one. Same
mistake as the `not TECHNICAL` claim in Experiment 1c — caught there by an
ablation, caught here only by being challenged on it.

`PromptTemplate.run()` now defaults to `temperature=0.0`; raising it is a
deliberate act reserved for experiments where variance is the subject (Week 3
self-consistency).

**Reproducible ≠ representative.** Temperature 0 yields the single most-likely
output — the prompt's best shot. A system deployed at 0.7 exposes users to the
full range, including weaker draws. Two different questions:

| question | how to evaluate |
|---|---|
| what is this prompt *capable* of? | temperature 0, one run |
| what will users actually *get*? | production temperature, 5–10 runs, report the spread |

Only the first was done here.

**Corollary:** non-determinism also makes judge validation impossible. A judge
verdict can't be checked against an output that no longer exists.

---

### Experiment 2b — Building a grounded LLM-as-judge

Prose output can't be scored by string comparison. Two ways to use a model as
the scorer:

| approach | prompt | ground truth | bias exposure |
|---|---|---|---|
| holistic | "Rate this review 1–5 for thoroughness" | none | maximum |
| **grounded** | "Here is one specific defect. Does this review identify it? YES/NO" | planted issue list | much lower |

`checklist_scorer.py` implements the grounded form: one binary question per
known defect. The judge never decides what "good" means — that was decided when
`planted_issues` was written. It only checks presence.

> An automated scorer is not more *correct* than a human. It is more
> *consistent* and it *scales*. Its accuracy comes entirely from the ground
> truth it's given.

**Metrics:** `issue_recall`, `critical_recall` (restricted to critical+high — an
80% recall that missed the SQL injection is worse than a 60% that caught it),
`severity_agreement`.

**Judge validation — the step that must come first.** A new judge gets checked
against cases whose answers are already known, before being trusted on cases
that aren't. Run against the `friendly`/`user_lookup` output, which had been
read manually:

| judge verdict | review text | correct |
|---|---|---|
| `sql_injection` ✓ critical | 🔴 Critical | ✅ |
| `bare_except` ✓ medium | 🟡 | ✅ |
| `mutable_default` ✓ medium | 🟡 | ✅ |
| `none_deref` ✗ | only `if row:` in refactor, never described | ✅ |
| `unused_import` ✗ | absent | ✅ |

5/5, including the hard case — it refused to credit a silent fix, per an explicit
instruction in the judge prompt.

**Severity agreement was broken until the scale was defined.** First run:
20–57% across every template. When every rater disagrees with your ground truth,
the ground truth is the outlier. The real defect was that "trivial" and "medium"
were never *defined* — the judge was mapping the review's colour-coding onto an
undefined scale and inventing the difference. Adding a rubric keyed to
consequence (`critical` = exploitable / `high` = wrong behaviour in normal use /
`medium` = conditional or maintainability / `trivial` = no behavioural impact)
moved agreement to 67–80%.

**Blind spot found:** `float_money` was missed by all three personas in the
temp-0.7 run. No prompt-level persona change surfaces it — it needs the defect
class named explicitly, or a different model.

---

### Experiment 3 — Structured output extraction

**Task:** Extract order details into a 5-field JSON schema (`order_id`,
`customer`, `date`, `quantity`, `unit_price`), 12 cases stratified
`clean / reordered / missing_field / distractor`.

- `extract_plain` — schema only
- `extract_strict` — schema + *"Return ONLY the raw JSON object. No markdown
  code fences, no commentary, no preamble."*

**Scorer:** `json_match` — parses both sides, ignores key order, gives partial
credit per field. Deliberately strips markdown fences before comparing, since
penalising fences would measure formatting rather than extraction. That made a
second metric necessary.

| Template | Passed | Mean | Cost |
|---|---|---|---|
| `extract_plain` | 12/12 | 1.00 | $0.004366 |
| `extract_strict` | 12/12 | 1.00 | $0.004586 |

| By hardness | clean | reordered | missing_field | distractor |
|---|---|---|---|---|
| both templates | 3/3 | 3/3 | 3/3 | 3/3 |

**Raw format compliance:**

| Template | bare | fenced | prose |
|---|---|---|---|
| `extract_plain` | 0/12 | **12/12** | 0/12 |
| `extract_strict` | 0/12 | **12/12** | 0/12 |

**Observations:**

**Extraction itself is solved.** Perfect across every category. `missing_field`
is the notable one — three cases have a genuinely absent value and the schema
says emit `null`. Predicted the model might invent a value to satisfy the
schema; it did not, every time. No hallucination under schema pressure.
`distractor` also clean: it never grabbed the referenced-but-wrong order number,
or the sales rep's name instead of the customer's.

**The format instruction had zero effect.** 24 of 24 responses fenced, including
all 12 from the template explicitly forbidding fences. Not reduced — unchanged.
This quantifies the Month 0 observation.

**Contrast with Experiment 1b, which is the interesting part.** There, a prose
rule overrode a prior strong enough to produce *below-chance* scoring (1/8 →
8/8). Here an equally explicit prose rule moved nothing. Same technique,
opposite outcome.

Hypothesis (untested): the routing prior is a **judgment** — which category does
this belong to — and stateable rules can redirect judgment. Fencing is a
**surface-form generation habit**, learned from a training corpus in which
essentially every code block is fenced. Closer to reflex than belief.

**Some behaviours cannot be prompted away.** This is the argument for Week 2.
The fix is not a better instruction but a mechanism that makes non-conforming
output impossible:

| approach | what it does |
|---|---|
| constrained decoding | restricts emittable tokens; output is guaranteed to parse |
| tool calling | model returns a structured call, not prose containing JSON |
| retry-on-invalid | catch the parse failure in code, re-prompt with the error |
| strip downstream | what `json_match` does — works, but a patch that breaks on the first unanticipated format |

**Eval note:** accuracy tied at ceiling *and* format tied at floor, so neither
metric separates these two prompts. The strict instruction is 20 tokens of
prompt with no measurable effect on anything — a template to delete rather than
keep.

---

### Experiment 3b — Pydantic validation, flat schema

**Question:** how often does a model emit structurally invalid output?

`Order` — 5 flat fields, pattern on `order_id`, `gt=0` on `quantity`. Two
strictness settings, two models, 12 cases each.

| | Claude | GPT-4o |
|---|---|---|
| lenient (`pydantic_match`) | 12/12 | 12/12 |
| strict (`pydantic_strict_match`) | 12/12 | 12/12 |
| cost | $0.004366 | $0.010025 (2.3×) |

**Failure rate: 0%, 48 responses.** Strict passing means both models emitted
real JSON integers and floats, never `"3"` for `3`. The lenient/strict gap that
motivated `OrderStrict` measured zero — coercion was never needed.

**Determinism confirmed in the numbers.** Cost was byte-identical between the
two runs per model ($0.004366 twice; $0.010025 twice). Same prompt at
temperature 0 produced identical token counts. Visible proof the temp fix works.

**Strict mode has a trap: JSON has no date type.** A blanket
`ConfigDict(strict=True)` rejects every ISO date string, since dates always
arrive as `"2026-03-04"`. Looks rigorous, is simply broken — it would measure
the wire format rather than the model. Strictness has to be applied per field,
based on what the wire format can actually represent.

**Fencing replicates on GPT-4o.** 0/12 bare on both models — 48/48 fenced
across two providers. Experiment 3's finding was not Claude-specific.

**Consequence:** a 0% failure rate leaves the retry loop nothing to catch. Drove
the harder schema below.

---

### Experiment 3c — Hard schema: where extraction actually breaks

`HardOrder` adds the constraint types models genuinely get wrong: an **enum**
(status), **format patterns** (SKU, ISO-4217 currency), a **nested list** of
line items, and a **cross-field validator** requiring `subtotal` to equal
`sum(quantity × unit_price)`.

10 cases, stratified. Failures at last.

| | Claude | GPT-4o |
|---|---|---|
| overall | 8/10 (0.80) | 7/10 (0.78) |
| status_inference | 4/4 | 4/4 |
| words_to_numbers | 2/2 | 1/2 |
| distractor | 2/2 | 2/2 |
| **arithmetic_load** | **0/2** | **0/2** |

**The failure is computation, not extraction.** Both models failed 100% of the
arithmetic cases while handling everything else well — inferring `shipped` from
"left our warehouse Tuesday", reading `£` as GBP, and correctly excluding a
stated $15 shipping charge from the subtotal on both distractor cases. Every
individual field right; the derived field wrong.

**That's a schema design flaw, not just a model limitation.** Asking a language
model to sum `2×9.99 + 3×4.50 + 1×22.00 + 5×1.20` requests something Python does
perfectly and free:

```python
items    = extract(text)                                    # model is good at this
subtotal = sum(i.quantity * i.unit_price for i in items)    # code is perfect at this
```

> Never ask the model for a value you can compute from values it already gave
> you.

**The subtler finding — validation catches malformed, not wrong.** GPT-4o's
extra 0.08 of mean score came from one case that *validated successfully with
bad data*: text said "out for delivery since Monday", model returned
`status: pending`. Correct answer is `shipped`.

| failure type | caught by |
|---|---|
| malformed JSON | the parser |
| wrong type, invalid enum value, bad format | Pydantic |
| inconsistent arithmetic | cross-field validator |
| **wrong enum choice** | **nothing but ground truth** |

`pending` is a valid enum member. Types correct, arithmetic consistent, every
check green — and the data is wrong. No schema catches this, because the error
is a judgment rather than a violation. It's also the same shape as the
Experiment 1b convention problem: mapping "out for delivery" onto a four-value
enum is a convention the model can't infer.

**Two labels in this test set are wrong.** That case is tagged
`words_to_numbers` because I assumed the spelled-out price would be the
difficulty. The model read "ninety-nine cents" as `0.99` without trouble; the
status broke. The stratification records what I *expected* to be hard, not what
is — same lesson as the math traps in Experiment 6.

**Method note.** I speculated on the cause of that partial score before reading
the log, and was wrong — guessed a price misparse, it was the status field.
Second time this month an explanation preceded the evidence. Checking cost one
command.

---

### Experiment 4 — Tool calling

**Setup:** identical task, test set, schema and scorer as Experiment 3c. Only
the output channel changes, so any difference is attributable to the channel.

- **Prose JSON** — ask for JSON in the reply, then strip fences, regex for
  braces, `json.loads`, validate.
- **Tool calling** — send a JSON Schema as a tool definition with
  `tool_choice` forcing its use. The model's answer arrives in a structured
  field the API has already parsed.

The tool schema is generated by `HardOrder.model_json_schema()` — the same
Pydantic model that validates the result, so schema and validator cannot drift.

**Note on the name:** nothing is executed. `record_order` does not exist as
code. The tool mechanism is being used purely as a structured-output channel,
which is a standard technique. The model emits *arguments*; whether anything
runs is the caller's business.

| | prose | tool calling |
|---|---|---|
| Claude | 8/10 | 8/10 |
| GPT-4o | 7/10 | 8/10 |
| **fenced (both models)** | **10/10** | **0/10** |
| **arithmetic_load (both)** | **0/2** | **0/2** |

**Observations:**

**Fences went to zero, not fewer.** An explicit prose instruction banning code
fences achieved nothing across 48 responses (Experiments 3 and 3b). Changing the
channel eliminated them entirely. The difference is structural rather than
persuasive: with no message body, there is nowhere for a fence to appear.

**Arithmetic is untouched** — 0/2 on both models, both providers, with different
wrong subtotals each time. The clean statement:

> Tool calling eliminates format failures completely and does nothing for
> reasoning failures.

That's a more precise claim than "tool calling is more reliable," and it names
which failure class each mechanism owns.

**Why it works — three things, only one of which is usually mentioned:**

1. The schema *is* a prompt. It's injected into context; the model reads it as
   text. Not fundamentally different from writing the schema into the prompt.
2. The output channel is parsed by the API. Structural.
3. **The format is trained, not merely requested.** Models are fine-tuned to
   emit well-formed tool calls. Compliance is far higher than for an arbitrary
   prose instruction, because one is an optimised capability and the other is a
   request competing with everything else in training.

(Some providers additionally offer constrained decoding, restricting sampleable
tokens so invalid output is impossible. Whether that was active here is
unverified.)

**Unpredicted: GPT-4o improved 7/10 → 8/10.** The `status: pending` error on
"out for delivery" did not recur. At temperature 0 that is not variance.
Hypothesis: the enum as a first-class schema constraint is more salient than the
same options described in prose. One case — hypothesis, not finding.

**Unpredicted: cost moved in opposite directions.**

| | prose | tool | change |
|---|---|---|---|
| Claude | $0.006826 | $0.014914 | **2.2× more** |
| GPT-4o | $0.013973 | $0.012677 | 0.9× |

Likely cause: JSON Schema is verbose — `$defs`, a `title` on every field, `$ref`
indirection — against a compact hand-written prose schema. Those tokens ride on
every request. "Use tool calling for reliability" is not free.

**Provider asymmetry worth remembering:** Anthropic returns tool input as a
*dict*; OpenAI returns a JSON *string* requiring `json.loads`. Same concept,
different plumbing — as with the system-prompt difference in Month 0.

---

### Experiment 5 — Retry-on-invalid vs. not delegating the computation

Three arms on the same 10 cases, both providers. Failures are entirely
arithmetic (Experiments 3c and 4): every line item extracted correctly, the
subtotal wrong.

- **no_retry** — single attempt, baseline
- **retry** — return the `ValidationError` as a `tool_result` marked
  `is_error`, up to 3 attempts
- **computed** — remove `subtotal` from the schema (`OrderNoSubtotal`) and
  calculate it in Python from the extracted items

| provider | arm | passed | recovered | cost | attempts |
|---|---|---|---|---|---|
| Claude | no_retry | 8/10 | — | $0.014906 | 1×10 |
| Claude | **retry** | **10/10** | 2 | $0.018722 (+26%) | 1×8, 2×2 |
| Claude | **computed** | **10/10** | — | $0.015394 (+3%) | 1×10 |
| GPT-4o | no_retry | 8/10 | — | $0.012677 | 1×10 |
| GPT-4o | **retry** | **10/10** | 2 | $0.016608 (+31%) | 1×8, 2×2 |
| GPT-4o | **computed** | **10/10** | — | $0.015253 | 1×10 |

**Observations:**

**Retry recovers 100%, always on attempt 2.** No case needed a third. Showing
the model its own rejected call plus the specific error was sufficient — the
correct line items were already in its context, so the correction is a re-add
rather than a re-extraction.

**Latency is the real cost, not tokens.** Retries are *sequential* API calls,
not parallel. +26–31% on spend, but a doubling of latency on every failing
request. At a 20% failure rate that lands directly on p95.

**The categorical difference:**

> Retry buys a high probability. Removing the delegation buys a certainty.

Retry went 2/2 here, but it is still a language model doing arithmetic with a
second attempt. Nothing guarantees convergence — a harder sum or a different
sample could fail twice and exhaust the budget. `sum(i.quantity * i.unit_price
for i in items)` is correct for every input that will ever exist. One is a
measurement, the other a proof.

**When retry is nonetheless the right tool:** when no deterministic fix exists.
A wrong enum choice or a misread field has no Python expression that repairs it
— the options are retry, escalate, or accept. That is the normal situation for
agents, which is why the loop was worth building despite being the wrong answer
for *this* task.

**The protocol matters — this is the agent loop, not a re-prompt.** The error
returns as a `tool_result` in the same conversation, so the model sees its own
call and the rejection:

```
user       "extract this order"
assistant  tool_use(record_order, {... subtotal: 75.45})
user       tool_result(is_error=True, "subtotal 75.45 does not match items")
assistant  tool_use(record_order, {... subtotal: 69.97})
```

Anthropic: `role="user"` with a `tool_result` content block.
OpenAI: `role="tool"` with `tool_call_id`.

**Bounded is load-bearing.** `MAX_ATTEMPTS = 3`. Uncapped retries are how agents
burn thousands overnight — the model gets stuck, re-calls with near-identical
arguments, and never converges. Cap it and count the attempts.

---

### Experiment 6 — Chain-of-thought

**Task:** Math word problems, 16 cases stratified `1step / 2step / multistep /
trap`. Traps are the classic counterintuitive ones (bat-and-ball, lily pad,
5 machines).
**Scorer:** `numeric_match` — extracts the final number, since CoT returns
working followed by `ANSWER: <n>`. Scoring that with `exact_match` would mark
every correct CoT answer wrong and report a 0% that is purely a scorer artifact.

| Version | Passed | Mean | Cost |
|---|---|---|---|
| `math_direct` | 13/16 | 0.81 | $0.001150 |
| `math_cot` | **16/16** | **1.00** | $0.010762 (**9.4×**) |

**By hardness:**

| | 1step | 2step | multistep | trap |
|---|---|---|---|---|
| direct | 4/4 | 3/4 | **2/4** | **4/4** |
| CoT | 4/4 | 4/4 | 4/4 | 4/4 |

**Observations:**

**Human-hard and model-hard are different things.** Direct answered every trap
correctly — the problems specifically designed to defeat intuition — while
failing half the multistep problems, which are conceptually trivial. The traps
are famous enough to be effectively memorised from training data; the model
isn't reasoning past the intuition, it's recalling the answer. What actually
breaks a model is *depth of sequential computation*.

**Why CoT works — autoregression.** Generation is token by token, and each
generated token becomes input for the next. Writing "24 × 0.25 = 6" puts that
intermediate result into the context, so the next step conditions on it. Without
CoT the model must jump question→answer in a single forward pass. CoT buys
**test-time compute**: more output tokens means more computation per problem.
It doesn't make the model smarter, it gives it more steps to think in.

**CoT bought nothing on easy problems and cost 9.4× anyway.** 4/4 both ways on
1step. All of CoT's value came from 2step and multistep. That points at adaptive
compute as the production pattern: classify difficulty first, route simple
queries to direct and hard ones to CoT, rather than paying the CoT tax on every
request.

**Method note:** all three pre-registered predictions held — CoT ≥ direct, traps
not actually hard for the model, cost multiple 5–10×. First experiment this
month where the prediction survived contact with the data.

---

### Experiment 7a — Self-consistency on math (a null result, and a repeated mistake)

`math_cot` scored 16/16 on the original set, so a harder one was built:
`math_hard.json`, 12 problems — compound percentages, multi-stage profit,
work-rate, mixture, optimisation.

| arm | samples | temp | passed | cost |
|---|---|---|---|---|
| single_temp0 | 1 | 0.0 | 12/12 | $0.013374 |
| single_temp07 | 1 | 0.7 | 12/12 | $0.014066 |
| self_consist | 5 | 0.7 | 12/12 | $0.069208 (**4.9×**) |

Agreement: **5/5 on all 12 cases.**

**Observations:**

**The test set failed to discriminate, and the reason is a repeated error.**
The problems were chosen using *human* difficulty intuitions — compound
interest, mixture algebra, work-rate. But Experiment 6 established that
human-hard ≠ model-hard: the classic traps were trivial because they're
memorised, while plain multistep arithmetic broke the model. Every problem here
is a standard textbook type, heavily represented in training data. Same mistake
as the traps, made again after learning it.

**Self-consistency bought nothing and cost 4.9×.** The technique has a
precondition that is easy to skip past: *the model must be failing sometimes.*
On a solved task it is pure waste.

**The real finding — temperature varies the path, not the destination.** At
temperature 0.7 the reasoning text differed between samples (different wording,
different intermediate framing) while the final answer was identical on all 12
problems, 5 times each.

> Temperature produces answer-level variance only where the model is genuinely
> uncertain.

This refines the earlier claim that "0.7 introduces variance". It does — in the
text. Whether it reaches the answer depends on whether the model is wobbling.
It also explains Experiment 2a, where temperature *did* flip results: those were
borderline cases.

**Consequence for the confidence hypothesis:** it *supports* the idea in
principle — answer disagreement should appear exactly where the model is unsure
— but it could not be tested here, because there were no low-agreement cases.
Untested, not disproved. See 7b.

---

### Experiment 7b — Self-consistency on a failure that reproduces

Rather than invent more math, this reuses the one failure that has appeared on
every single run: extraction arithmetic. Both models, prose JSON and tool
calling, temperature 0 — `arithmetic_load` fails 0/2 every time. Reliable
failure is precisely what self-consistency needs.

**The question:** is the arithmetic error *systematic* (same wrong answer each
time — voting cannot help) or *random* (different errors, truth modal — voting
recovers it)?

| arm | samples | temp | passed | cost |
|---|---|---|---|---|
| single_temp0 | 1 | 0.0 | 8/10 | $0.006706 |
| single_temp07 | 1 | 0.7 | 8/10 | $0.006554 |
| self_consist | 5 | 0.7 | **8/10** | $0.033636 (**5.1×**) |

**Agreement vs. correctness — the headline:**

| agreement | cases | correct |
|---|---|---|
| 5/5 | 8 | **8/8** |
| 1/5 | 2 | **0/2** |

**Perfect discrimination.** Every case where samples agreed was right; every
case where they scattered was wrong. The agreement-as-confidence hypothesis from
7a is confirmed — as strongly as 10 cases permit.

**The vote itself bought nothing**, and the reason is subtler than "systematic
error". The sampled subtotals:

```
case 3312 (expected 92.20):  75.7,  77.2,  77.7,  78.7,  79.7
case 9001 (expected 61.48):  64.47, 66.47, 68.47, 69.87, 79.78
```

**Five distinct values, so no majority exists.** The error is random but
**diffuse** — scattered rather than clustered. Self-consistency assumes errors
concentrate and truth is modal; with a flat error distribution there is nothing
to select.

**And the correct answer never appeared. Not once in ten samples.**

> Majority vote can only choose among answers the model actually generates. If
> truth is never sampled, no amount of voting finds it.

That is the fundamental limit of the technique, and it is rarely stated
alongside the recommendation. Self-consistency requires the correct answer to be
*reachable* — present in the distribution, merely not always top-ranked. Where
the model is scattered rather than wobbling, sampling only maps the error.

**Practical conclusion — the technique failed at its stated purpose and
succeeded at a better one.** 5× cost, zero accuracy gain, and a perfect
confidence signal. Run it not for the vote but for the disagreement
measurement, then route low-agreement cases to a human or a deterministic fix.

Which closes a loop with Experiment 5: the fix for these cases is computing the
subtotal in Python. Agreement tells you *which* cases need that treatment
**without access to ground truth** — which is the only version that works in
production.

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
