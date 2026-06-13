# LLM Comparison — Month 0 Deliverable
**Author:** Rev Bobba  
**Date started:** 2026-06-07  
**Models tested:** claude-haiku-4-5, GPT-4o

---

## Models Overview

| Model | Provider | Context Window | Input price (1M tokens) | Output price (1M tokens) |
|-------|----------|---------------|------------------------|--------------------------|
| claude-haiku-4-5 | Anthropic | 200K | $0.80 | $4.00 |
| gpt-4o | OpenAI | 128K | $2.50 | $10.00 |

---

## Observational Lenses
*Fill these in as patterns emerge across all 10 experiments. Don't answer upfront — let the data tell you.*

### Instruction Following
Does the model follow explicit constraints (word limits, format rules, output schemas)?  
**Claude:** Tends to exceed constraints — ignored 150-word limit, and softened "no English" directive by adding comments inside code blocks. Interprets instructions expansively.  
**GPT-4o:** More literal and conservative — stayed within word limit, and gave minimal compliant output when told "code only."  
> Experiment 1: GPT-4o followed 150-word limit (~126 words). Claude did not (~172 words).  
> Experiment 7: Both softened "no plain English" when phrased loosely. Both complied fully when phrased strictly ("No English text whatsoever. Not even a single sentence.")  
> Key lesson: Precision in system prompt wording matters. Vague constraints get softened; explicit ones get followed.

### Hallucination vs. Uncertainty
When the answer is unknown or ambiguous, does the model make something up or admit uncertainty?  
**Claude:** _(fill in)_  
**GPT-4o:** _(fill in)_

### Consistency at Temperature=0
Run the same prompt 3x at temp=0. Are outputs near-identical?  
**Claude:** Perfectly deterministic — identical output all 3 runs.  
**GPT-4o:** Perfectly deterministic — identical output all 3 runs.  
> Both models behave as expected at temp=0. At temp=1, Claude varied more meaningfully; GPT-4o stayed closer to its default phrasing, suggesting a more peaked distribution for this prompt type.

### Format / JSON Compliance
When asked for a specific JSON schema, does the output parse cleanly every time?  
**Claude:** _(fill in)_  
**GPT-4o:** _(fill in)_

### Long Context Degradation
Ask a question about content near the end of a long document. Does the model lose track of earlier content?  
**Claude:** Handled up to 110K tokens cleanly with consistent responses. Failed gracefully at 207K with a clear error message. Response quality and latency were stable across all sizes tested.  
**GPT-4o:** Could not be tested above ~30K tokens — account TPM rate limit (30K/min) blocks oversized requests before they reach the model. This is an account tier constraint, not a model limitation.  
> Key lesson: Context limit and rate limit are different things. Claude's 200K is a hard model constraint. GPT-4o's 128K context limit is real, but hitting it requires a higher OpenAI tier first.

### Cost vs. Quality Tradeoff
For which task types is the cheaper model (claude-haiku-4-5) good enough vs. where does GPT-4o justify the price?  
_(fill in after all 10 experiments)_

### Latency
Which model is consistently faster across experiments?  
**Claude avg latency:** _(fill in)_  
**GPT-4o avg latency:** _(fill in)_

### Audience Awareness
Does the model tailor its response to the specified audience (e.g. "explain like I'm a SWE")?  
**Claude:** _(fill in)_  
**GPT-4o:** _(fill in)_  
> Experiment 1 finding: Claude picked up on the SWE framing and ended with a code-style breakdown (`Input: String, Output: String`). GPT-4o gave a more generic explanation that could have been written for anyone.

### When I'd pick each model
*(Fill in after all 10 experiments)*  
**Claude haiku-4-5:** _(tasks where you'd choose it)_  
**GPT-4o:** _(tasks where you'd choose it)_

---

## Experiment Results

### Experiment 1: Factual Question
**Prompt:** "What is a large language model? Explain it like I'm a software engineer who has never worked in ML."  
**System prompt:** "You are a helpful assistant. Be concise — 150 words max."  
**Temperature:** 0.7 (default)

| | claude-haiku-4-5 | GPT-4o |
|-|-------------------|--------|
| Response (first 200 chars) | "Think of it as a **massive statistical pattern-matching engine** trained on billions of text examples..." | "A large language model (LLM) is a type of artificial intelligence designed to understand and generate human-like text..." |
| Tokens in / out | 46 / 230 | 46 / 168 |
| Cost | $0.000957 | $0.001795 |
| Latency (ms) | 3,923 | 7,010 |
| My notes | Used markdown headers and structure unprompted. More tokens but cheaper due to lower output price. **Did NOT follow the 150-word limit** (~172 words). | Plain prose, more concise. Nearly 2x the cost and 2x slower despite fewer tokens — higher per-token price. **Followed the 150-word limit** (~126 words). |

---

### Experiment 2: Creative Writing
**Prompt:** _(paste your prompt here)_

| | Claude 3.5 Sonnet | GPT-4o |
|-|-------------------|--------|
| Response | | |
| My notes | | |

---

### Experiment 3: Code Generation
**Prompt:** _(paste your prompt here)_

| | Claude 3.5 Sonnet | GPT-4o |
|-|-------------------|--------|
| Code correct? (Y/N) | | |
| Explained clearly? | | |
| My notes | | |

---

### Experiment 4: Long Document Summary
_Paste a long article (1000+ words) and ask both to summarize in 100 words._

| | Claude 3.5 Sonnet | GPT-4o |
|-|-------------------|--------|
| Summary | | |
| What was missed? | | |

---

### Experiment 5: JSON Extraction
**Prompt:** _(ask the model to extract structured data from unstructured text as JSON)_

| | Claude 3.5 Sonnet | GPT-4o |
|-|-------------------|--------|
| Valid JSON returned? | | |
| Schema followed? | | |

---

### Experiment 6: Temperature 0.0 vs 1.0
**Prompt:** "Write a one-sentence tagline for a new AI startup."  
**Runs:** 3x at each temperature to test consistency

| | temp=0.0 (run 1) | temp=0.0 (run 2) | temp=0.0 (run 3) |
|-|-----------------|-----------------|-----------------|
| Claude | "Intelligent automation that learns your business, so you can focus on what matters." | identical | identical |
| GPT-4o | "Empowering Tomorrow with Smarter Solutions Today." | identical | identical |

| | temp=1.0 (run 1) | temp=1.0 (run 2) | temp=1.0 (run 3) |
|-|-----------------|-----------------|-----------------|
| Claude | "Intelligence, automated—so you can focus on what actually matters." | "Turning complexity into clarity, one intelligent solution at a time." | "Turning complex data into clear decisions, instantly." |
| GPT-4o | "Revolutionizing Tomorrow: Unleashing the Power of Intelligent Possibilities Today." | "Empower Tomorrow: AI Solutions for a Smarter World Today." | "Empowering Tomorrow with Smarter AI Solutions Today." |

**Observations:**
- temp=0 was perfectly deterministic for both models — identical output every run
- Claude varied more meaningfully at temp=1 — three genuinely different angles (automation, clarity, data)
- GPT-4o barely changed at temp=1 — all three were structural variations of "Empowering Tomorrow with X Today" — suggesting its distribution is more peaked for this prompt type
- **Practical rule:** use temp=0 for consistency (extraction, classification, structured output); use temp=0.7–1.0 for variety (creative tasks, brainstorming)

---

### Experiment 7: With vs. Without System Prompt
**Prompt:** "Explain recursion to a software engineer."  
**System prompt (loose):** "You are a senior software engineer who explains concepts using code examples only. Never use analogies or plain English — always show code."  
**System prompt (strict):** "You are a senior software engineer who explains concepts using code examples only. Respond with code only. No English text whatsoever. Not even a single sentence."

| | No system prompt | Loose system prompt | Strict system prompt |
|-|------------------|--------------------|--------------------|
| Claude tokens out | _(run to get)_ | _(run to get)_ | 821 |
| GPT-4o tokens out | _(run to get)_ | _(run to get)_ | 46 |
| Claude cost | — | — | $0.003323 |
| GPT-4o cost | — | — | $0.000580 |
| Claude latency | — | — | 4,428ms |
| GPT-4o latency | — | — | 685ms |
| Claude notes | — | Small English blurb remained | 7 code examples: factorial, fibonacci, memoization, tree traversal, recursion vs iteration, binary search, mutual recursion |
| GPT-4o notes | — | Small English blurb remained | 1 code example: factorial only |

**What changed with system prompt:**
- GPT-4o got *cheaper* after system prompt — response became more focused, shorter output tokens outweighed extra input tokens (output is 4x more expensive than input)
- Claude got *more expensive* — interpreted "show code" as license to be maximally thorough, producing 7 examples vs GPT-4o's 1
- Both softened the loose "never use plain English" instruction; both fully complied with the strict version

**Key insight:** GPT-4o is more literal/conservative — minimally compliant. Claude is more expansive — maximally helpful within the constraint. Neither is wrong; depends on your use case.

---

### Context Window Experiment
**Prompt:** "Summarize this in one sentence:" + repeated text scaled by multiplier  
**System prompt:** "Be concise."  
**Tool:** Anthropic `count_tokens` API (Claude) + `tiktoken` (GPT-4o) for pre-flight estimates

| Multiplier | Claude tokens (est → actual) | GPT-4o tokens (est → actual) | Claude cost | GPT-4o cost | Claude latency | GPT-4o result |
|---|---|---|---|---|---|---|
| 1x | 127 → 131 | 109 → 123 | $0.000165 | $0.000418 | 2,680ms | ✅ OK |
| 10x | 1,117 → 1,121 | 1,009 → 1,023 | $0.000957 | $0.002668 | 681ms | ✅ OK |
| 100x | 11,017 → 11,021 | 10,009 → 10,023 | $0.008877 | $0.025167 | 886ms | ✅ OK |
| 500x | 55,017 → 55,021 | 50,009 → 0 | $0.044089 | — | 1,391ms | ❌ 429 TPM rate limit |
| 1000x | 110,017 → 110,021 | 100,009 → 0 | $0.088073 | — | 2,223ms | ❌ 429 TPM rate limit |
| 2000x | 220,017 → 0 | 200,009 → 0 | — | — | 602ms | ❌ 429 TPM rate limit |

**Observations:**
- Pre-flight estimates were accurate — Claude within 4 tokens, GPT-4o within 14 tokens (difference is system prompt tokens not counted by tiktoken)
- Claude and GPT-4o tokenizers disagree by ~10% on the same input (e.g. 127 vs 109 at 1x) — same text, different token boundaries
- Cost scales perfectly linearly with token count — no bulk discount
- Latency does NOT scale linearly — mostly network/queue variance, not input length
- Claude failed cleanly at 2000x with a descriptive error: `prompt is too long: 207808 tokens > 200000 maximum`
- GPT-4o never hit its 128K context limit — the 30K TPM account rate limit blocked every request above ~30K tokens

---

### Experiment 8: Chain-of-Thought
**Add "Think step by step before answering."**

| | Without CoT | With CoT |
|-|-------------|----------|
| Claude quality (1-5) | | |
| GPT-4o quality (1-5) | | |
| Token cost increase | | |

---

### Experiment 9: Adversarial / Guardrails
**What I tried:** _(describe the prompt)_  
**Claude response:** _(how did it handle it?)_  
**GPT-4o response:** _(how did it handle it?)_  
**Observations:**

---

### Experiment 10: Cost Comparison
**Task:** _(same task run on both)_

| | Claude 3.5 Sonnet | GPT-4o |
|-|-------------------|--------|
| Tokens in | | |
| Tokens out | | |
| Total cost | | |
| Quality (1-5) | | |
| Cost/quality winner | | |

---

## My Conclusions

### When I'd pick Claude:
_(write this based on your experiments, not from articles)_

### When I'd pick GPT-4o:
_(write this based on your experiments)_

### Biggest surprise:
_(something you didn't expect)_

### Cost estimate for a 1000-user app (1 call/user/day):
- Claude 3.5 Sonnet: ~$___/month
- GPT-4o: ~$___/month
- _(show your math)_

---

## Resources Used
- Anthropic Pricing: https://docs.anthropic.com/en/docs/about-claude/models/overview
- OpenAI Pricing: https://openai.com/api/pricing
