# Month 0: AI Landscape Explorer
**Part of Rev's AI Engineer Roadmap 2026**

> A Python script that calls Claude and GPT-4o in parallel, logs responses, token counts, and cost per call. The foundation for 10 structured LLM comparison experiments.

---

## What this does

- Calls Claude 3.5 Sonnet and GPT-4o with the same prompt **in parallel** (using asyncio)
- Logs every call to a structured JSON-lines file: model, response, tokens, cost, latency
- Provides a template for running 10 comparison experiments (see `llm_comparison.md`)

---

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/[your-username]/ai-roadmap-m0-landscape
cd ai-roadmap-m0-landscape

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up API keys
cp .env.example .env
# Edit .env and paste your Anthropic and OpenAI API keys

# 5. Run
python api_explorer.py
```

---

## What I learned

_(fill this in after completing Month 0 experiments — write it in your own words)_

- 
- 
- 

---

## Cost

Running all 10 experiments costs approximately $___. Each individual call is typically $0.001–$0.01 depending on prompt length and model.

---

## Files

| File | Purpose |
|------|---------|
| `api_explorer.py` | Main script — extend this each week |
| `llm_comparison.md` | Written analysis of all 10 experiments |
| `logs/` | JSON-lines experiment logs (gitignored) |
| `requirements.txt` | Python dependencies |
| `.env.example` | API key template |

---

## Next: Month 1 — Prompt Engineering
[github.com/[you]/ai-roadmap-m1-prompting] _(link when built)_
