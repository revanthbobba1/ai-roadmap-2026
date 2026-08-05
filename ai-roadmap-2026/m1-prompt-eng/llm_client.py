"""
llm_client.py — Month 1
AI Roadmap 2026 | Rev Bobba

Carried over from Month 0's api_explorer.py. This is the working API layer —
you shouldn't need to change much here. Month 1's new work lives in
prompt_library.py and eval_harness.py.

Provides:
  - LLMResponse       : structured record of one API call
  - call_claude()     : async Anthropic call with retry
  - call_openai()     : async OpenAI call with retry
  - compare()         : both models in parallel
  - save_log()        : append a response to logs/YYYY-MM-DD.jsonl
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

import anthropic
import openai
from dotenv import load_dotenv

load_dotenv(override=True)

# ── Pricing (USD per 1M tokens — update if prices change) ─────────────────────
# Source: https://docs.anthropic.com/en/docs/about-claude/models/overview
#         https://openai.com/api/pricing
PRICING = {
    "claude-haiku-4-5": {"input": 0.80, "output": 4.00},
    "gpt-4o":           {"input": 2.50, "output": 10.00},
    "gpt-4o-mini":      {"input": 0.15, "output": 0.60},
}


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
            preview = self.response[:500]
            print(f"Response:\n{preview}{'...' if len(self.response) > 500 else ''}")
        print(f"{'='*60}")


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


async def with_exponential_backoff(fn, max_retries: int = 4):
    """
    Retry an async API call on rate limit errors using exponential backoff.
    Waits 1s, 2s, 4s, 8s between attempts before giving up.
    All other errors are re-raised immediately without retrying.
    """
    for attempt in range(max_retries):
        try:
            return await fn()
        except (anthropic.RateLimitError, openai.RateLimitError):
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt
            print(f"  ⏳ Rate limited. Retrying in {wait}s "
                  f"(attempt {attempt + 1}/{max_retries})...")
            await asyncio.sleep(wait)


async def call_claude(
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    model: str = "claude-haiku-4-5",
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> LLMResponse:
    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    start = time.time()
    try:
        message = await with_exponential_backoff(lambda: client.messages.create(
            model=model, max_tokens=max_tokens, temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        ))
        latency_ms = int((time.time() - start) * 1000)
        tokens_in, tokens_out = message.usage.input_tokens, message.usage.output_tokens
        return LLMResponse(
            model=model, prompt=prompt, system_prompt=system_prompt,
            response=message.content[0].text,
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
        completion = await with_exponential_backoff(lambda: client.chat.completions.create(
            model=model, temperature=temperature, max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        ))
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
