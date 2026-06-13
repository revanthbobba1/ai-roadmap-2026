"""
api_explorer.py — Month 0
AI Roadmap 2026 | Rev Bobba

Each experiment lives in its own function. To run one, uncomment it in main().

SETUP:
  1. pip install -r requirements.txt
  2. Copy .env.example to .env and add your real API keys
  3. Run: python api_explorer.py
"""

import asyncio
import json
import time
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import anthropic
import openai
import tiktoken

load_dotenv(override=True)

# ── Pricing (USD per 1M tokens — update if prices change) ─────────────────────
# Source: https://docs.anthropic.com/en/docs/about-claude/models/overview
#         https://openai.com/api/pricing
PRICING = {
    "claude-haiku-4-5": {"input": 0.80, "output": 4.00},
    "gpt-4o":           {"input": 2.50, "output": 10.00},
    "gpt-4o-mini":      {"input": 0.15, "output": 0.60},
}

# Published context limits (tokens) — update if models change
# Sources: https://docs.anthro pic.com/en/docs/about-claude/models/overview
#          https://platform.openai.com/docs/models
CONTEXT_LIMITS = {
    "claude-haiku-4-5": 200_000,
    "gpt-4o":           128_000,
    "gpt-4o-mini":      128_000,
}


# ── Core data structure ────────────────────────────────────────────────────────

@dataclass
class LLMResponse:
    model: str
    prompt: str
    system_prompt: str
    response: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    timestamp: str
    error: str = ""

    def display(self):
        print(f"\n{'='*60}")
        print(f"Model:    {self.model}")
        print(f"Tokens:   {self.tokens_in} in / {self.tokens_out} out")
        print(f"Cost:     ${self.cost_usd:.6f}")
        print(f"Latency:  {self.latency_ms}ms")
        if self.error:
            print(f"ERROR:    {self.error}")
        else:
            print(f"Response:\n{self.response[:500]}{'...' if len(self.response) > 500 else ''}")
        print(f"{'='*60}")


# ── Helpers ────────────────────────────────────────────────────────────────────

def calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    if model not in PRICING:
        return 0.0
    p = PRICING[model]
    return (tokens_in * p["input"] + tokens_out * p["output"]) / 1_000_000


def save_log(response: LLMResponse, log_dir: str = "logs"):
    Path(log_dir).mkdir(exist_ok=True)
    log_file = Path(log_dir) / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(asdict(response)) + "\n")


def summary(label: str, claude_r: LLMResponse, openai_r: LLMResponse):
    print(f"\n{'='*60}")
    print(f"SUMMARY — {label}")
    print(f"{'='*60}")
    print(f"{'':20} {'Claude':20} {'GPT-4o':20}")
    print(f"{'Tokens in':20} {claude_r.tokens_in:<20} {openai_r.tokens_in:<20}")
    print(f"{'Tokens out':20} {claude_r.tokens_out:<20} {openai_r.tokens_out:<20}")
    print(f"{'Cost':20} ${claude_r.cost_usd:<19.6f} ${openai_r.cost_usd:<19.6f}")
    print(f"{'Latency (ms)':20} {claude_r.latency_ms:<20} {openai_r.latency_ms:<20}")
    print(f"\n💰  Total: ${claude_r.cost_usd + openai_r.cost_usd:.6f}")


# ── API callers ────────────────────────────────────────────────────────────────

async def call_claude(
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    model: str = "claude-haiku-4-5",
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> LLMResponse:
    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    start = time.time()
    try:
        message = await client.messages.create(
            model=model, max_tokens=max_tokens, temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        latency_ms = int((time.time() - start) * 1000)
        tokens_in, tokens_out = message.usage.input_tokens, message.usage.output_tokens
        return LLMResponse(
            model=model, prompt=prompt, system_prompt=system_prompt,
            response=message.content[0].text, tokens_in=tokens_in, tokens_out=tokens_out,
            cost_usd=calculate_cost(model, tokens_in, tokens_out),
            latency_ms=latency_ms, timestamp=datetime.now().isoformat(),
        )
    except Exception as e:
        return LLMResponse(
            model=model, prompt=prompt, system_prompt=system_prompt,
            response="", tokens_in=0, tokens_out=0, cost_usd=0.0,
            latency_ms=int((time.time() - start) * 1000),
            timestamp=datetime.now().isoformat(), error=str(e),
        )


async def call_openai(
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    model: str = "gpt-4o",
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> LLMResponse:
    client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    start = time.time()
    try:
        completion = await client.chat.completions.create(
            model=model, temperature=temperature, max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )
        latency_ms = int((time.time() - start) * 1000)
        tokens_in = completion.usage.prompt_tokens
        tokens_out = completion.usage.completion_tokens
        return LLMResponse(
            model=model, prompt=prompt, system_prompt=system_prompt,
            response=completion.choices[0].message.content,
            tokens_in=tokens_in, tokens_out=tokens_out,
            cost_usd=calculate_cost(model, tokens_in, tokens_out),
            latency_ms=latency_ms, timestamp=datetime.now().isoformat(),
        )
    except Exception as e:
        return LLMResponse(
            model=model, prompt=prompt, system_prompt=system_prompt,
            response="", tokens_in=0, tokens_out=0, cost_usd=0.0,
            latency_ms=int((time.time() - start) * 1000),
            timestamp=datetime.now().isoformat(), error=str(e),
        )


async def compare(
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    temperature: float = 0.7,
    log: bool = True,
) -> tuple[LLMResponse, LLMResponse]:
    """Call Claude and GPT-4o in parallel. Returns (claude, openai)."""
    claude_r, openai_r = await asyncio.gather(
        call_claude(prompt, system_prompt, temperature=temperature),
        call_openai(prompt, system_prompt, temperature=temperature),
    )
    if log:
        save_log(claude_r)
        save_log(openai_r)
    return claude_r, openai_r


# ══════════════════════════════════════════════════════════════════════════════
# EXPERIMENTS
# ══════════════════════════════════════════════════════════════════════════════

# ── Experiment 1: Factual Question ────────────────────────────────────────────
async def experiment_1_factual_question():
    """Week 1 — First API call. Same factual question to both models."""
    print("\n🚀  Experiment 1: Factual Question\n")
    prompt = "What is a large language model? Explain it like I'm a software engineer who has never worked in ML."
    system = "You are a helpful assistant. Be concise — 150 words max."
    claude_r, openai_r = await compare(prompt, system_prompt=system)
    claude_r.display()
    openai_r.display()
    summary("Experiment 1", claude_r, openai_r)


# ── Experiment 6: Temperature ─────────────────────────────────────────────────
async def experiment_6_temperature():
    """Week 2 — Run same prompt 3x at temp=0 and temp=1 to observe determinism vs. variety."""
    print("\n🚀  Experiment 6: Temperature (0.0 vs 1.0)\n")
    prompt = "Write a one-sentence tagline for a new AI startup."
    for temp in [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]:
        print(f"\n--- Temperature: {temp} ---")
        claude_r, openai_r = await compare(prompt, system_prompt="", temperature=temp, log=False)
        print(f"Claude:  {claude_r.response.strip()}")
        print(f"GPT-4o:  {openai_r.response.strip()}")


# ── Experiment 7: System Prompt ───────────────────────────────────────────────
async def experiment_7_system_prompt():
    """Week 2 — Compare loose vs. strict system prompt instruction following."""
    print("\n🚀  Experiment 7: System Prompt\n")
    prompt = "Explain recursion to a software engineer."

    print("=" * 60)
    print("PART A: No system prompt")
    print("=" * 60)
    claude_a, openai_a = await compare(prompt, system_prompt="")
    claude_a.display()
    openai_a.display()

    print("\n" + "=" * 60)
    print("PART B: Loose system prompt ('code examples only')")
    print("=" * 60)
    loose = "You are a senior software engineer who explains concepts using code examples only. Never use analogies or plain English — always show code."
    claude_b, openai_b = await compare(prompt, system_prompt=loose)
    claude_b.display()
    openai_b.display()

    print("\n" + "=" * 60)
    print("PART C: Strict system prompt ('no English whatsoever')")
    print("=" * 60)
    strict = "You are a senior software engineer who explains concepts using code examples only. Respond with code only. No English text whatsoever. Not even a single sentence."
    claude_c, openai_c = await compare(prompt, system_prompt=strict)
    claude_c.display()
    openai_c.display()

    total = sum(r.cost_usd for r in [claude_a, openai_a, claude_b, openai_b, claude_c, openai_c])
    print(f"\n💰  Total cost: ${total:.6f}")


# ── Experiment: Context Window ────────────────────────────────────────────────
async def experiment_context_window():
    """Week 2 — Feed increasingly long inputs to find token limits and cost scaling."""
    print("\n🚀  Context Window Experiment\n")
    base_text = "The quick brown fox jumps over the lazy dog. " * 10
    # Anthropic provides a pre-flight token counter; OpenAI does not, so we
    # use Anthropic's count as the estimate for both (same input text = ~same tokens).
    count_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    for multiplier in [1, 10, 100, 500, 1000, 2000]:
        text = base_text * multiplier
        prompt = f"Summarize this in one sentence:\n\n{text}"

        # Pre-flight token estimates (no API call needed)
        # Anthropic: official count_tokens API
        claude_token_count = count_client.messages.count_tokens(
            model="claude-haiku-4-5",
            messages=[{"role": "user", "content": prompt}]
        )
        estimated_claude_tokens = claude_token_count.input_tokens

        # OpenAI: tiktoken (same tokenizer GPT models use internally)
        enc = tiktoken.encoding_for_model("gpt-4o")
        estimated_openai_tokens = len(enc.encode(prompt))

        est_cost_claude = (estimated_claude_tokens * PRICING["claude-haiku-4-5"]["input"]) / 1_000_000
        est_cost_openai = (estimated_openai_tokens * PRICING["gpt-4o"]["input"]) / 1_000_000

        print(f"\n{'='*60}")
        print(f"Multiplier: {multiplier}x")
        print(f"Pre-flight → Claude: {estimated_claude_tokens} tokens (${est_cost_claude:.6f}) | GPT-4o: {estimated_openai_tokens} tokens (${est_cost_openai:.6f})")

        claude_limit = CONTEXT_LIMITS["claude-haiku-4-5"]
        openai_limit = CONTEXT_LIMITS["gpt-4o"]

        if estimated_claude_tokens > claude_limit:
            print(f"⚠️  {estimated_claude_tokens} tokens exceeds Claude limit ({claude_limit:,}) — expect an error")
        if estimated_openai_tokens > openai_limit:
            print(f"⚠️  {estimated_openai_tokens} tokens exceeds GPT-4o limit ({openai_limit:,}) — expect an error")

        claude_r, openai_r = await compare(prompt, system_prompt="Be concise.", log=False)

        print(f"\nClaude  → tokens in: {claude_r.tokens_in} | out: {claude_r.tokens_out} | latency: {claude_r.latency_ms}ms | cost: ${claude_r.cost_usd:.6f}")
        if claude_r.error:
            print(f"  ERROR: {claude_r.error}")
        else:
            print(f"  Response: {claude_r.response[:120].strip()}...")

        print(f"GPT-4o  → tokens in: {openai_r.tokens_in} | out: {openai_r.tokens_out} | latency: {openai_r.latency_ms}ms | cost: ${openai_r.cost_usd:.6f}")
        if openai_r.error:
            print(f"  ERROR: {openai_r.error}")
        else:
            print(f"  Response: {openai_r.response[:120].strip()}...")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN — uncomment the experiment you want to run
# ══════════════════════════════════════════════════════════════════════════════

async def main():
    # await experiment_1_factual_question()
    # await experiment_6_temperature()
    # await experiment_7_system_prompt()
    await experiment_context_window()


if __name__ == "__main__":
    asyncio.run(main())
