# Prompt Engineering & Evaluation — Month 1 Analysis

**Rev Bobba | AI Engineer Roadmap 2026**

Models tested: `claude-haiku-4-5` (Anthropic), `gpt-4o` (OpenAI)

---

## Section 1: Techniques Tested

| Technique | Definition | Status |
|-----------|------------|--------|
| Zero-shot | Instruction only, no examples | ⬜ |
| Few-shot | Instruction + 2–3 worked examples | ⬜ |
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

### Experiment 1 — Zero-shot vs. few-shot

**Task:** Support ticket routing (BILLING / TECHNICAL / ACCOUNT / OTHER)
**Test set:** `test_sets/ticket_routing.json` — 20 hand-labeled tickets

| Prompt version | Passed | Mean score | Cost |
|---|---|---|---|
| `ticket_router_zero_shot` | _(fill in)_ | | |
| `ticket_router_few_shot` | | | |

**Observations:**
_(fill in)_

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
