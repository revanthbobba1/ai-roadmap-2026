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
**Claude:** _(fill in)_  
**GPT-4o:** _(fill in)_  
> Experiment 1 finding: GPT-4o followed the 150-word limit (~126 words). Claude did not (~172 words).

### Hallucination vs. Uncertainty
When the answer is unknown or ambiguous, does the model make something up or admit uncertainty?  
**Claude:** _(fill in)_  
**GPT-4o:** _(fill in)_

### Consistency at Temperature=0
Run the same prompt 3x at temp=0. Are outputs near-identical?  
**Claude:** _(fill in)_  
**GPT-4o:** _(fill in)_

### Format / JSON Compliance
When asked for a specific JSON schema, does the output parse cleanly every time?  
**Claude:** _(fill in)_  
**GPT-4o:** _(fill in)_

### Long Context Degradation
Ask a question about content near the end of a long document. Does the model lose track of earlier content?  
**Claude:** _(fill in)_  
**GPT-4o:** _(fill in)_

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
**Same prompt, different temperatures:**

| | temp=0.0 | temp=1.0 |
|-|----------|----------|
| Claude response | | |
| GPT-4o response | | |
| Observations | | |

---

### Experiment 7: With vs. Without System Prompt
| | No system prompt | With system prompt |
|-|------------------|-------------------|
| Claude | | |
| GPT-4o | | |
| What changed? | | |

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
