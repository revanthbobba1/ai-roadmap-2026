"""
tool_calling.py — Month 1, Week 2 Day 3-4

Extraction via TOOL CALLING instead of asking for JSON in prose.

THE DIFFERENCE
--------------
Prose JSON:   "return JSON matching this schema" -> model writes text that
              hopefully parses. Experiment 3 measured 48/48 responses wrapped
              in markdown fences despite an explicit instruction not to.

Tool calling: you hand the provider a JSON Schema. The model emits a structured
              function call, and the API returns parsed arguments. There is no
              prose layer, so there is nothing to fence.

Both providers take standard JSON Schema, generated here from the same Pydantic
model that validates the result — so the schema and the validator cannot drift.

WIRE FORMAT DIFFERS, CONCEPT IS IDENTICAL
------------------------------------------
Anthropic   tools=[{name, description, input_schema}]
            tool_choice={"type": "tool", "name": ...}
            result at message.content[i].input  (already a dict)

OpenAI      tools=[{type: "function", function: {name, description, parameters}}]
            tool_choice={"type": "function", "function": {"name": ...}}
            result at ...tool_calls[0].function.arguments  (a JSON string)

Note the asymmetry: Anthropic hands back a dict, OpenAI a string you must parse.
Same trap as the system-prompt difference from Month 0 — the concept ports, the
plumbing doesn't.

WHAT THIS SHOULD AND SHOULD NOT FIX
-----------------------------------
Should fix    fencing, malformed JSON, missing fields, wrong types — anything
              about the SHAPE of the output
Should NOT fix arithmetic errors, wrong enum choices — anything about the
              CONTENT. A schema constrains form, not correctness.

Run:  python tool_calling.py
"""

import asyncio
import json
import os
import time

import anthropic
import openai
from dotenv import load_dotenv

from llm_client import PRICING, calculate_cost, with_exponential_backoff
from schemas import HardOrder

load_dotenv(override=True)

TOOL_NAME = "record_order"
TOOL_DESCRIPTION = (
    "Record the structured details of a customer order extracted from free text. "
    "subtotal must equal the sum of quantity x unit_price across all items, "
    "excluding shipping and tax."
)

PROMPT = "Extract the order details from this text and record them.\n\nText: {text}"


def tool_schema() -> dict:
    """JSON Schema straight from the Pydantic model — single source of truth."""
    return HardOrder.model_json_schema()


# ── Providers ─────────────────────────────────────────────────────────────────

async def call_claude_tool(text: str, model: str = "claude-haiku-4-5") -> dict:
    """Returns {"raw": <json str>, "cost_usd": float, "latency_ms": int, "error": str}."""
    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    start = time.time()
    try:
        msg = await with_exponential_backoff(lambda: client.messages.create(
            model=model,
            max_tokens=1024,
            temperature=0.0,
            tools=[{
                "name": TOOL_NAME,
                "description": TOOL_DESCRIPTION,
                "input_schema": tool_schema(),
            }],
            # Force the tool rather than letting the model choose prose.
            tool_choice={"type": "tool", "name": TOOL_NAME},
            messages=[{"role": "user", "content": PROMPT.format(text=text)}],
        ))
        block = next((b for b in msg.content if b.type == "tool_use"), None)
        if block is None:
            return _err("model returned no tool_use block", start)
        return {
            "raw": json.dumps(block.input),   # already a dict; re-serialise to score
            "cost_usd": calculate_cost(model, msg.usage.input_tokens,
                                       msg.usage.output_tokens),
            "latency_ms": int((time.time() - start) * 1000),
            "error": "",
        }
    except Exception as e:
        return _err(str(e), start)


async def call_openai_tool(text: str, model: str = "gpt-4o") -> dict:
    client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    start = time.time()
    try:
        comp = await with_exponential_backoff(lambda: client.chat.completions.create(
            model=model,
            temperature=0.0,
            tools=[{
                "type": "function",
                "function": {
                    "name": TOOL_NAME,
                    "description": TOOL_DESCRIPTION,
                    "parameters": tool_schema(),
                },
            }],
            tool_choice={"type": "function", "function": {"name": TOOL_NAME}},
            messages=[{"role": "user", "content": PROMPT.format(text=text)}],
        ))
        calls = comp.choices[0].message.tool_calls
        if not calls:
            return _err("model returned no tool_calls", start)
        return {
            # OpenAI hands back a STRING here, Anthropic a dict. Same concept,
            # different plumbing.
            "raw": calls[0].function.arguments,
            "cost_usd": calculate_cost(model, comp.usage.prompt_tokens,
                                       comp.usage.completion_tokens),
            "latency_ms": int((time.time() - start) * 1000),
            "error": "",
        }
    except Exception as e:
        return _err(str(e), start)


def _err(msg: str, start: float) -> dict:
    return {"raw": "", "cost_usd": 0.0,
            "latency_ms": int((time.time() - start) * 1000), "error": msg}


# ── Experiment ────────────────────────────────────────────────────────────────

async def run(model: str = "claude"):
    from eval_harness import hard_order_match

    cases = json.load(open("test_sets/entity_extraction_hard.json"))
    caller = call_claude_tool if model == "claude" else call_openai_tool

    results = await asyncio.gather(*[
        caller(c["variables"]["text"]) for c in cases
    ])

    rows, cost, fenced = [], 0.0, 0
    for case, r in zip(cases, results):
        if r["error"]:
            raise RuntimeError(f"tool call failed: {r['error']}")
        cost += r["cost_usd"]
        if r["raw"].strip().startswith("```"):
            fenced += 1
        ok, score, note = hard_order_match(r["raw"], case["expected"])
        rows.append((case["hardness"], ok, score, note))

    passed = sum(1 for _, ok, _, _ in rows if ok)
    print(f"\n{'='*70}")
    print(f"TOOL CALLING — {model}")
    print(f"{'='*70}")
    print(f"Passed:   {passed}/{len(rows)}")
    print(f"Mean:     {sum(s for _, _, s, _ in rows)/len(rows):.2f}")
    print(f"Fenced:   {fenced}/{len(rows)}   <- structured output, so nothing to fence")
    print(f"Cost:     ${cost:.6f}")

    by = {}
    for h, ok, _, _ in rows:
        p, t = by.get(h, (0, 0))
        by[h] = (p + int(ok), t + 1)
    print("\n  by hardness")
    for h, (p, t) in sorted(by.items()):
        print(f"    {h:<20} {p}/{t}")

    fails = [(h, n) for h, ok, _, n in rows if not ok]
    if fails:
        print("\n  failures")
        for h, n in fails:
            print(f"    {h:<20} {n[:60]}")
    print(f"{'='*70}")
    return rows


async def main():
    for m in ["claude", "openai"]:
        await run(m)


if __name__ == "__main__":
    asyncio.run(main())
