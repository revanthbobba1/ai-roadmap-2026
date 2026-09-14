"""
one_turn.py — Month 2, Week 1 Day 1-2

The single round trip, with every step printed.

WHY THIS FILE EXISTS SEPARATELY FROM agent.py
---------------------------------------------
The loop in agent.py is this, repeated. Get the round trip working and visible
first; generalising it afterwards is a `while` and an iteration counter.

THE FOUR STEPS
--------------
  1. send   the user's question + the list of tools available
  2. receive a tool_use block — the model saying "call search_jobs with these args"
  3. execute the tool yourself and send the result back as tool_result
  4. receive the final text answer

Step 3 is the part Month 1 never did. Month 1 forced a single tool call and read
the arguments; it never fed a result back or let the model continue.

Run:  python one_turn.py
      python one_turn.py "any question you like"
"""

import json
import os
import sys

import anthropic
from dotenv import load_dotenv

import tools  # noqa: F401 — importing registers search_jobs
from tools import registry

load_dotenv(override=True)

MODEL = "claude-haiku-4-5"
DEFAULT_QUESTION = "What backend engineer jobs are available in Boston?"

SYSTEM_PROMPT = (
    "You are a job application assistant. Use the tools available to you. "
    "Prefer looking something up over guessing."
)


def show(label: str, obj):
    print(f"\n{'='*72}\n{label}\n{'='*72}")
    print(obj if isinstance(obj, str) else json.dumps(obj, indent=2, default=str))


def main():
    question = " ".join(sys.argv[1:]) or DEFAULT_QUESTION
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # The conversation. This list is the agent's entire memory — every turn
    # appends to it, which is why multi-turn agents get expensive.
    messages = [{"role": "user", "content": question}]

    show("STEP 1 — what we send", {
        "system": SYSTEM_PROMPT,
        "messages": messages,
        "tools": [t["name"] for t in registry.specs("claude")],
    })

    # ── Turn 1: the model decides to call a tool ──────────────────────────────
    msg = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages,
        tools=registry.specs("claude"),
    )

    show("STEP 2 — what comes back", {
        "stop_reason": msg.stop_reason,
        "content_block_types": [b.type for b in msg.content],
    })

    # stop_reason == "tool_use" means the model wants a tool run before it can
    # answer. The alternative is "end_turn", meaning it answered directly — which
    # is what happens for a question needing no tool.
    tool_uses = [b for b in msg.content if b.type == "tool_use"]
    if not tool_uses:
        text = "".join(b.text for b in msg.content if b.type == "text")
        print("\nModel answered without calling a tool:\n")
        print(text)
        return

    block = tool_uses[0]
    print(f"\n  it wants:  {block.name}({json.dumps(block.input)})")
    print(f"  block id:  {block.id}      <- needed to match the result back")

    # ── Execute the tool ourselves ────────────────────────────────────────────
    # Nothing is executed automatically. The model proposed a call; running it
    # is entirely our decision, which is where every guardrail in Week 3 lives.
    tool = registry.get(block.name)
    args = tool.args_model.model_validate(block.input)   # schema validation
    result = tool.fn(args, None)

    show("STEP 3 — the tool's output (we produced this, not the model)", result)

    # ── Append BOTH messages ──────────────────────────────────────────────────
    # This is the part people get wrong. Two messages, not one:
    #   the assistant's turn (containing the tool_use block), then
    #   a user turn carrying the tool_result.
    # Skip the assistant message and the API rejects the tool_result as
    # referencing a tool_use that isn't in the conversation.
    messages.append({"role": "assistant", "content": msg.content})
    messages.append({"role": "user", "content": [{
        "type": "tool_result",
        "tool_use_id": block.id,     # must match the block's id exactly
        "content": result,
    }]})

    print(f"\n  conversation is now {len(messages)} messages: "
          f"{[m['role'] for m in messages]}")

    # ── Turn 2: the model answers, now that it has the data ───────────────────
    final = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages,
        tools=registry.specs("claude"),
    )

    text = "".join(b.text for b in final.content if b.type == "text")
    show("STEP 4 — the final answer", text)

    total_in = msg.usage.input_tokens + final.usage.input_tokens
    total_out = msg.usage.output_tokens + final.usage.output_tokens
    print(f"\n  2 API calls | {total_in} in / {total_out} out")
    print(f"  turn 1 input: {msg.usage.input_tokens} tokens")
    print(f"  turn 2 input: {final.usage.input_tokens} tokens   <- grew, because")
    print(f"                the tool call and its result are now in the context")


if __name__ == "__main__":
    main()
