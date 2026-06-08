"""
api_explorer.py — Month 0 Starter Script
AI Roadmap 2026 | Rev Bobba

PURPOSE:
  Call Claude and GPT-4o with the same prompt, log responses, token counts, and cost.
  Extend this script each week as you learn more.

SETUP:
  1. pip install anthropic openai python-dotenv
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

load_dotenv(override=True)

# ── Pricing (USD per 1M tokens, update as models change) ──────────────────────
PRICING = {
    "claude-haiku-4-5":           {"input": 0.80, "output": 4.00},
    "gpt-4o":                     {"input": 2.50, "output": 10.00},
    "gpt-4o-mini":                {"input": 0.15, "output": 0.60},
}

@dataclass
class LLMResponse:
    """Structured container for a single LLM call result."""
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


def calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Calculate USD cost for a call given token counts."""
    if model not in PRICING:
        return 0.0
    p = PRICING[model]
    return (tokens_in * p["input"] + tokens_out * p["output"]) / 1_000_000


def save_log(response: LLMResponse, log_dir: str = "logs"):
    """Append response to a JSON-lines log file."""
    Path(log_dir).mkdir(exist_ok=True)
    log_file = Path(log_dir) / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(asdict(response)) + "\n")


# ── Claude ────────────────────────────────────────────────────────────────────

async def call_claude(
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    model: str = "claude-haiku-4-5",
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> LLMResponse:
    """Call Claude asynchronously and return a structured LLMResponse."""
    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    start = time.time()
    try:
        message = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        latency_ms = int((time.time() - start) * 1000)
        tokens_in = message.usage.input_tokens
        tokens_out = message.usage.output_tokens
        return LLMResponse(
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            response=message.content[0].text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=calculate_cost(model, tokens_in, tokens_out),
            latency_ms=latency_ms,
            timestamp=datetime.now().isoformat(),
        )
    except Exception as e:
        return LLMResponse(
            model=model, prompt=prompt, system_prompt=system_prompt,
            response="", tokens_in=0, tokens_out=0, cost_usd=0.0,
            latency_ms=int((time.time() - start) * 1000),
            timestamp=datetime.now().isoformat(), error=str(e),
        )


# ── OpenAI ────────────────────────────────────────────────────────────────────

async def call_openai(
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    model: str = "gpt-4o",
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> LLMResponse:
    """Call OpenAI GPT-4o asynchronously and return a structured LLMResponse."""
    client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    start = time.time()
    try:
        completion = await client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )
        latency_ms = int((time.time() - start) * 1000)
        tokens_in = completion.usage.prompt_tokens
        tokens_out = completion.usage.completion_tokens
        return LLMResponse(
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            response=completion.choices[0].message.content,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=calculate_cost(model, tokens_in, tokens_out),
            latency_ms=latency_ms,
            timestamp=datetime.now().isoformat(),
        )
    except Exception as e:
        return LLMResponse(
            model=model, prompt=prompt, system_prompt=system_prompt,
            response="", tokens_in=0, tokens_out=0, cost_usd=0.0,
            latency_ms=int((time.time() - start) * 1000),
            timestamp=datetime.now().isoformat(), error=str(e),
        )


# ── Parallel runner ───────────────────────────────────────────────────────────

async def compare(
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    temperature: float = 0.7,
    log: bool = True,
) -> tuple[LLMResponse, LLMResponse]:
    """Call Claude and GPT-4o in parallel with the same prompt. Returns both responses."""
    claude_result, openai_result = await asyncio.gather(
        call_claude(prompt, system_prompt, temperature=temperature),
        call_openai(prompt, system_prompt, temperature=temperature),
    )
    if log:
        save_log(claude_result)
        save_log(openai_result)
    return claude_result, openai_result


# ── Main experiments ──────────────────────────────────────────────────────────

async def main():
    print("🚀  API Explorer — Month 0")
    print("Running Experiment 1: same factual question to both models...\n")

    prompt = "What is a large language model? Explain it like I'm a software engineer who has never worked in ML."
    system = "You are a helpful assistant. Be concise — 150 words max."

    claude_r, openai_r = await compare(prompt, system_prompt=system)
    claude_r.display()
    openai_r.display()

    total_cost = claude_r.cost_usd + openai_r.cost_usd
    print(f"\n💰  Total cost for this experiment: ${total_cost:.6f}")
    print(f"📁  Logged to logs/{datetime.now().strftime('%Y-%m-%d')}.jsonl")
    print("\n--- Next step: try changing the prompt and temperature, then run again. ---")
    print("--- See the Month 0 guide doc for the full list of 10 experiments. ---")


if __name__ == "__main__":
    asyncio.run(main())
