# LLM Comparison — Month 0 Deliverable
**Author:** Rev Bobba  
**Date started:** _(fill in)_  
**Models tested:** Claude 3.5 Sonnet, GPT-4o, _(add Gemini if you get to stretch goals)_

---

## Models Overview

| Model | Provider | Context Window | Input price (1M tokens) | Output price (1M tokens) |
|-------|----------|---------------|------------------------|--------------------------|
| claude-3-5-sonnet-20241022 | Anthropic | 200K | $3.00 | $15.00 |
| gpt-4o | OpenAI | 128K | $2.50 | $10.00 |
| _(add row)_ | | | | |

---

## Experiment Results

### Experiment 1: Factual Question
**Prompt:** _(paste your prompt here)_  
**System prompt:** _(paste if used)_  
**Temperature:** _(value)_

| | Claude 3.5 Sonnet | GPT-4o |
|-|-------------------|--------|
| Response (first 200 chars) | | |
| Tokens in / out | | |
| Cost | | |
| Latency (ms) | | |
| My notes | | |

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
