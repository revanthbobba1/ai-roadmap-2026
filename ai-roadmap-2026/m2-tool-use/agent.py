"""
agent.py — Month 2, Week 1

The ReAct loop. This file is deliberately incomplete: writing the loop IS the
Week 1 exercise, and it is about 40 lines.

WHAT THE LOOP IS
----------------
    user      "find me backend jobs in Boston"
    model     tool_use(search_jobs, {query: "backend", location: "Boston"})
    you       execute it -> "Found 4 jobs: ..."
    model     <- tool_result appended to the conversation
    model     tool_use(get_job_details, {job_id: "j_003"})
    you       execute it -> "..."
    model     <- tool_result
    model     "Here are three worth looking at..."        <- text, so we stop

Reasoning and acting interleave in one conversation. That is ReAct, and it is
what makes multi-step questions possible — the model cannot know which job to
detail until the search comes back.

WHAT MONTH 1 ALREADY BUILT
--------------------------
The outbound half: tool schemas from Pydantic models, and sending them with the
request. Month 1 forced a single tool call and stopped there.

The new part is everything after: feeding the result back as a tool_result and
letting the model continue until it produces text instead of another call.

WIRE FORMAT, BOTH PROVIDERS
---------------------------
  Anthropic   assistant message content contains a ToolUseBlock (.id, .name,
              .input as a dict). You reply with a user message whose content is
              a tool_result block referencing tool_use_id.

  OpenAI      assistant message has .tool_calls (.id, .function.arguments as a
              JSON STRING — parse it). You reply with role="tool" and
              tool_call_id.

Same concept, different plumbing. Month 1 hit this asymmetry too.

Run:  python agent.py "find me backend engineer jobs in Boston"
"""

import json
import os
import sys

import anthropic
from dotenv import load_dotenv

import tools  # noqa: F401 — importing registers the tools
from guardrails import TOOL_RISK, GuardrailViolation, Session, apply_guardrails
from llm_client import calculate_cost
from tools import registry

load_dotenv(override=True)

MODEL = "claude-haiku-4-5"
MAX_ITERATIONS = 8

# The Anthropic API defaults to temperature 1.0. Left unset, the same question
# produces different tool arguments each run — "backend engineer" one time,
# "backend" the next — which makes Week 4's trajectory comparison meaningless.
#
# Agents are never fully deterministic even at 0, because each turn conditions
# on the last and small differences compound. But 0 removes the sampling noise,
# leaving only the compounding, which is the thing worth measuring.
#
# Raise it deliberately when studying variance (pass^k in Week 4), never by
# accident. Same rule as Month 1's PromptTemplate.run().
TEMPERATURE = 0.0

SYSTEM_PROMPT = """You are a job application assistant. You help the user find \
roles, track applications, and draft follow-ups.

Use the tools available to you. Prefer looking something up over guessing. If a \
question does not require a tool — general advice about job searching, for \
example — answer directly rather than calling one.

Never take an irreversible action without being explicit about what you are \
about to do."""


def execute_tool(name: str, raw_args: dict, session: Session) -> str:
    """
    Validate, guard, and run one tool call.

    Returns the string that goes back to the model as a tool_result. Errors are
    returned as strings rather than raised, because the model should SEE the
    failure and get a chance to correct — the same bounded self-correction
    pattern as Month 1's retry loop.
    """
    try:
        tool = registry.get(name)
    except KeyError as e:
        return f"ERROR: {e}"

    try:
        # 1. schema validation — types, ranges, and extra="forbid", which is
        #    what stops the model supplying a parameter it shouldn't have.
        args = tool.args_model.model_validate(raw_args)

        # 2. guardrails — budget, and (Week 3) validation, idempotency, approval
        apply_guardrails(name, args.model_dump(), session)
        session.budget.record(TOOL_RISK[name])

        # 3. run it, passing the SESSION as context.
        #
        #    Server-side parameters travel here, not in `args`. The session is
        #    trusted state; the arguments are model-supplied. Keeping them in
        #    separate channels is the whole point — a tool reads ctx.owner and
        #    there is no path by which the model could have influenced it.
        #
        #    (An earlier version injected `owner` into the args dict and then
        #    re-validated. extra="forbid" rejected it — the guardrail fighting
        #    the schema, which is a sign the parameter was in the wrong channel.)
        return tool.fn(args, session)
    except GuardrailViolation as e:
        return f"REFUSED: {e}"
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"


class IterationCapExceeded(RuntimeError):
    """
    The agent ran out of turns without producing an answer.

    Deliberately its own exception type rather than a generic error, because
    Week 5 counts these: iteration-cap-hit-rate is the headline health metric.
    Agents that hit the cap are agents that got stuck, and the rate at which it
    happens is the best early warning you have in production.
    """


def run(user_message: str, session: Session,
        max_iterations: int = MAX_ITERATIONS,
        temperature: float = TEMPERATURE,
        verbose: bool = False) -> tuple[str, list[dict]]:
    """
    Run the agent until it produces a final answer or hits the iteration cap.

    Returns (final_text, trace). The trace is a list of turns, and it is the
    thing Week 4's trajectory eval scores and Week 5's tracing aggregates — so
    it records more than looks necessary right now.

    This is one_turn.py generalised: same four steps, wrapped in a loop, with
    support for several tool calls per turn.
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    messages: list[dict] = [{"role": "user", "content": user_message}]
    trace: list[dict] = []

    for turn in range(max_iterations):
        msg = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=registry.specs("claude"),
            # anthropic SDK 1.0 (2026-08-20) REMOVED temperature, top_p and
            # top_k from messages.create(). The Messages API still accepts
            # them; extra_body is the documented migration path — the SDK
            # merges this dict into the request JSON.
            #
            # Month 1's venv pinned an older SDK, so llm_client.py worked all
            # month passing temperature= directly. A fresh install resolves 1.x
            # and that call now raises TypeError.
            extra_body={"temperature": temperature},
        )

        cost = calculate_cost(MODEL, msg.usage.input_tokens, msg.usage.output_tokens)
        session.budget.usd_used += cost

        tool_uses = [b for b in msg.content if b.type == "tool_use"]

        # ── TERMINATION ───────────────────────────────────────────────────────
        # No tool call means the model is answering rather than acting. That is
        # the only clean exit; everything else falls through to the cap.
        if not tool_uses:
            final = "".join(b.text for b in msg.content if b.type == "text")
            # Record the answering turn too. Without it the trace undercounts
            # turns by one, and step-efficiency metrics in Week 4 would ignore
            # the cost of the turn that actually produced the answer.
            trace.append({
                "turn": turn, "tool": None, "args": None, "result": final,
                "refused": False, "errored": False,
                "input_tokens": msg.usage.input_tokens,
                "output_tokens": msg.usage.output_tokens,
                "cost_usd": cost,
            })
            if verbose:
                print(f"  [turn {turn}] answered ({msg.usage.input_tokens} in)")
            return final, trace

        # The assistant's turn must go in BEFORE the results, and must contain
        # the tool_use blocks — a tool_result referencing a tool_use that isn't
        # in the conversation is rejected.
        messages.append({"role": "assistant", "content": msg.content})

        results = []
        for block in tool_uses:
            out = execute_tool(block.name, block.input, session)

            trace.append({
                "turn": turn,
                "tool": block.name,
                "args": block.input,
                "result": out,
                "refused": out.startswith("REFUSED:"),
                "errored": out.startswith("ERROR:"),
                "input_tokens": msg.usage.input_tokens,
                "output_tokens": msg.usage.output_tokens,
                "cost_usd": cost,
            })

            if verbose:
                short = out.replace("\n", " ")[:60]
                print(f"  [turn {turn}] {block.name}({json.dumps(block.input)}) "
                      f"-> {short}")

            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": out,
            })

        # Several tool_results ride in ONE user message — one per tool_use the
        # model requested this turn.
        messages.append({"role": "user", "content": results})

    # Fell out of the loop. This is a failure, not a quiet degradation: the
    # agent never answered. Raising makes that impossible to ignore.
    raise IterationCapExceeded(
        f"hit iteration cap ({max_iterations}) after {len(trace)} tool calls. "
        f"last tool: {trace[-1]['tool'] if trace else 'none'}"
    )


def main():
    if len(sys.argv) < 2:
        print('usage: python agent.py "your question"')
        sys.exit(1)

    session = Session(owner=os.getenv("AGENT_OWNER", "rev"))
    print(f"tools: {list(registry.REGISTRY)}\n")

    try:
        final, trace = run(" ".join(sys.argv[1:]), session, verbose=True)
    except IterationCapExceeded as e:
        print(f"\nAGENT STUCK: {e}")
        sys.exit(2)

    print(f"\n{final}")

    # Context growth — the per-turn input token curve, which is the Week 1
    # measurement. Turn N pays for every turn before it.
    if trace:
        tool_calls = sum(1 for t in trace if t["tool"])
        turns = trace[-1]["turn"] + 1
        print(f"\n--- {tool_calls} tool calls over {turns} turns, "
              f"${session.budget.usd_used:.4f} ---")
        print(f"    {'turn':<6}{'tool':<22}{'input':<9}{'growth'}")
        prev = None
        for t in trace:
            delta = "" if prev is None else f"+{t['input_tokens'] - prev}"
            print(f"    {t['turn']:<6}{(t['tool'] or '(answered)'):<22}"
                  f"{t['input_tokens']:<9}{delta}")
            prev = t["input_tokens"]


if __name__ == "__main__":
    main()
