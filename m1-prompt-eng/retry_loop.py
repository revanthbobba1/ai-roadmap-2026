"""
retry_loop.py — Month 1, Week 2 Day 5-6

Bounded self-correction: when validation fails, hand the error back to the model
and let it try again.

THREE ARMS, because "does retrying work" is the less interesting question
-------------------------------------------------------------------------
  1. no_retry    single attempt. Baseline: 8/10 on both models.
  2. retry       on ValidationError, return the error and re-attempt, up to
                 MAX_ATTEMPTS. Measures recovery rate and the cost of it.
  3. computed    remove `subtotal` from the schema entirely and calculate it in
                 Python from the extracted line items.

Arm 3 exists because the only failures are arithmetic — both models extract
every underlying field correctly and then get the sum wrong. Retrying is
self-correction on a task that shouldn't have been delegated in the first place.
The comparison is the point: how good is a retry loop versus not needing one.

THE PROTOCOL — this is the real agent loop, not a re-prompt
------------------------------------------------------------
The error is returned as a `tool_result` marked as an error, in the same
conversation. The model sees its own previous call, then the failure, and
corrects. This is the pattern every agent framework implements underneath:

    user      "extract this order"
    assistant tool_use(record_order, {...subtotal: 75.45})
    user      tool_result(is_error=True, "subtotal 75.45 does not match items")
    assistant tool_use(record_order, {...subtotal: 69.97})

Anthropic  role="user" with a content block of type "tool_result"
OpenAI     role="tool" with tool_call_id

BOUNDED is doing work in that phrase. Uncapped retries are how agents burn
thousands of dollars overnight — the model gets stuck, calls the same tool with
near-identical arguments, and never converges.

Run:  python retry_loop.py
"""

import asyncio
import json
import os
import time

import anthropic
import openai
from dotenv import load_dotenv
from pydantic import ValidationError

from llm_client import calculate_cost, with_exponential_backoff
from schemas import HardOrder, OrderNoSubtotal

load_dotenv(override=True)

MAX_ATTEMPTS = 3          # 1 initial + 2 corrections
TOOL_NAME = "record_order"
PROMPT = "Extract the order details from this text and record them.\n\nText: {text}"

DESC_FULL = (
    "Record the structured details of a customer order extracted from free text. "
    "subtotal must equal the sum of quantity x unit_price across all items, "
    "excluding shipping and tax."
)
DESC_NO_SUBTOTAL = (
    "Record the structured details of a customer order extracted from free text. "
    "Record each line item exactly as stated; do not compute any totals."
)


# ── Anthropic ─────────────────────────────────────────────────────────────────

async def claude_attempt(messages, schema, description, model="claude-haiku-4-5"):
    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    msg = await with_exponential_backoff(lambda: client.messages.create(
        model=model, max_tokens=1024, temperature=0.0,
        tools=[{"name": TOOL_NAME, "description": description,
                "input_schema": schema}],
        tool_choice={"type": "tool", "name": TOOL_NAME},
        messages=messages,
    ))
    block = next((b for b in msg.content if b.type == "tool_use"), None)
    cost = calculate_cost(model, msg.usage.input_tokens, msg.usage.output_tokens)
    return msg, block, cost


async def run_claude(text, model_cls, description, max_attempts):
    """Returns (validated_obj_or_None, attempts_used, total_cost, errors_seen)."""
    schema = model_cls.model_json_schema()
    messages = [{"role": "user", "content": PROMPT.format(text=text)}]
    total_cost, errors = 0.0, []

    for attempt in range(1, max_attempts + 1):
        msg, block, cost = await claude_attempt(messages, schema, description)
        total_cost += cost
        if block is None:
            return None, attempt, total_cost, errors + ["no tool_use block"]

        try:
            return model_cls.model_validate(block.input), attempt, total_cost, errors
        except ValidationError as e:
            err = _fmt(e)
            errors.append(err)
            if attempt == max_attempts:
                return None, attempt, total_cost, errors
            # Feed the failure back as a tool_result. The model sees its own
            # call and why it was rejected — this is the agent loop.
            messages += [
                {"role": "assistant", "content": msg.content},
                {"role": "user", "content": [{
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "is_error": True,
                    "content": f"Validation failed: {err}. Correct it and call the tool again.",
                }]},
            ]
    return None, max_attempts, total_cost, errors


# ── OpenAI ────────────────────────────────────────────────────────────────────

async def run_openai(text, model_cls, description, max_attempts, model="gpt-4o"):
    client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    schema = model_cls.model_json_schema()
    messages = [{"role": "user", "content": PROMPT.format(text=text)}]
    total_cost, errors = 0.0, []

    for attempt in range(1, max_attempts + 1):
        comp = await with_exponential_backoff(lambda: client.chat.completions.create(
            model=model, temperature=0.0,
            tools=[{"type": "function", "function": {
                "name": TOOL_NAME, "description": description, "parameters": schema}}],
            tool_choice={"type": "function", "function": {"name": TOOL_NAME}},
            messages=messages,
        ))
        total_cost += calculate_cost(model, comp.usage.prompt_tokens,
                                     comp.usage.completion_tokens)
        call = (comp.choices[0].message.tool_calls or [None])[0]
        if call is None:
            return None, attempt, total_cost, errors + ["no tool_calls"]

        try:
            payload = json.loads(call.function.arguments)
            return model_cls.model_validate(payload), attempt, total_cost, errors
        except (ValidationError, json.JSONDecodeError) as e:
            err = _fmt(e) if isinstance(e, ValidationError) else f"invalid JSON: {e}"
            errors.append(err)
            if attempt == max_attempts:
                return None, attempt, total_cost, errors
            messages += [
                comp.choices[0].message,
                {"role": "tool", "tool_call_id": call.id,
                 "content": f"Validation failed: {err}. Correct it and call the tool again."},
            ]
    return None, max_attempts, total_cost, errors


def _fmt(e: ValidationError) -> str:
    first = e.errors()[0]
    loc = ".".join(map(str, first["loc"])) or "(object)"
    return f"{loc}: {first['msg']}"


# ── Experiment ────────────────────────────────────────────────────────────────

def _matches(obj, expected: dict, computed_subtotal: float | None = None) -> bool:
    """Compare a validated object against expected values."""
    got = json.loads(obj.model_dump_json())
    if computed_subtotal is not None:
        got["subtotal"] = round(computed_subtotal, 2)
    for k, v in expected.items():
        if k not in got:
            return False
        a, b = got[k], v
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            if abs(float(a) - float(b)) > 0.01:
                return False
        elif a != b:
            return False
    return True


async def arm(name: str, provider: str, model_cls, description, max_attempts,
              compute_subtotal: bool):
    cases = json.load(open("test_sets/entity_extraction_hard.json"))
    runner = run_claude if provider == "claude" else run_openai

    results = await asyncio.gather(*[
        runner(c["variables"]["text"], model_cls, description, max_attempts)
        for c in cases
    ])

    passed, cost, attempts_hist, recovered = 0, 0.0, {}, 0
    for case, (obj, attempts, c, errs) in zip(cases, results):
        cost += c
        attempts_hist[attempts] = attempts_hist.get(attempts, 0) + 1
        if obj is None:
            continue
        sub = None
        if compute_subtotal:
            sub = sum(i.quantity * i.unit_price for i in obj.items)
        if _matches(obj, json.loads(case["expected"]), sub):
            passed += 1
            if attempts > 1:
                recovered += 1

    return {"name": name, "provider": provider, "passed": passed,
            "total": len(cases), "cost": cost, "attempts": attempts_hist,
            "recovered": recovered}


async def main():
    rows = []
    for provider in ["claude", "openai"]:
        rows.append(await arm("no_retry", provider, HardOrder, DESC_FULL, 1, False))
        rows.append(await arm("retry", provider, HardOrder, DESC_FULL, MAX_ATTEMPTS, False))
        rows.append(await arm("computed", provider, OrderNoSubtotal,
                              DESC_NO_SUBTOTAL, 1, True))

    print(f"\n{'='*78}")
    print("RETRY LOOP vs COMPUTING THE DERIVED FIELD")
    print(f"{'='*78}")
    print(f"{'PROVIDER':<10}{'ARM':<12}{'PASSED':<10}{'RECOVERED':<12}{'COST':<12}{'ATTEMPTS'}")
    for r in rows:
        att = " ".join(f"{k}x{v}" for k, v in sorted(r["attempts"].items()))
        print(f"{r['provider']:<10}{r['name']:<12}"
              f"{r['passed']}/{r['total']:<8}{r['recovered']:<12}"
              f"${r['cost']:<11.6f}{att}")
    print(f"{'='*78}")
    print("  RECOVERED = passed only after a retry")
    print("  ATTEMPTS  = NxM means M cases finished in N attempts")


if __name__ == "__main__":
    asyncio.run(main())
