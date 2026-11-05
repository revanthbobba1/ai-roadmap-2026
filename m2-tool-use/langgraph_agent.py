"""
langgraph_agent.py — Month 2, Week 5

WHAT      The same agent as agent.py, rebuilt on LangGraph.
EXPORTS   run_langgraph(query, session, max_iterations) -> (final, trace)
          Same signature as agent.run, so agent_eval scores either one.
KEY       make_guarded_tools() is load-bearing. Without it the framework
          executes tools directly and the entire guardrail layer is bypassed —
          silently, because the tools themselves still work.

Run:  python langgraph_agent.py "which Boston job pays best?"

══════════════════════════ reasoning and notes below ══════════════════════════

WHY PORT RATHER THAN START HERE
-------------------------------
Having written the loop by hand first is the whole point. Most people who use
LangGraph have only ever used LangGraph, and cannot say what it does for them.
After agent.py, this comparison is available:

    hand-built   ~60 lines: the while loop, tool_use extraction, tool_result
                 construction, iteration cap, trace collection
    LangGraph    create_react_agent(model, tools) — one line

The interesting question is not which is shorter. It is what the one-liner
HIDES, and whether anything you cared about survives the port.

WHAT DID NOT SURVIVE AUTOMATICALLY
----------------------------------
The guardrails. create_react_agent executes tools directly — it calls the
function bound to each tool and feeds the result back. The whole
validate -> guard -> execute chain in agent.execute_tool is bypassed unless
every tool is explicitly wrapped.

That is the real integration work, and it is worth noticing: adopting an agent
framework does not automatically carry your safety layer with it. A team that
ports a working agent to LangGraph and forgets this ships an agent with no
budget, no business-rule validation, and no approval gate — while every test
still passes, because the tools themselves still work.

Each tool below is wrapped so guardrails still run. The wrapper is ~10 lines
and it is the only reason this port is safe.
"""

import os
import sys

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import StructuredTool

# FRAMEWORK CHURN, EXHIBIT A
# --------------------------
# The prebuilt moved packages AND renamed its parameters inside one major
# version. langgraph.prebuilt.create_react_agent(prompt=...) became
# langchain.agents.create_agent(system_prompt=...), with pre/post_model_hook
# replaced by a `middleware` list. The old path still works but warns, and is
# scheduled for removal in V2.0.
#
# Supporting both is three lines, and it is the honest answer to "what does a
# framework cost you": not the code you write, the code you rewrite when the
# framework moves. agent.py needed no changes across the same period.
try:
    from langchain.agents import create_agent as _create_agent
    _PROMPT_KW = "system_prompt"
except ImportError:                                  # langchain not installed
    from langgraph.prebuilt import create_react_agent as _create_agent
    _PROMPT_KW = "prompt"

import tools  # noqa: F401 — registers them
from agent import MODEL, SYSTEM_PROMPT, TEMPERATURE, execute_tool
from guardrails import Budget, Session
from llm_client import calculate_cost
from tools import registry

load_dotenv(override=True)


def make_guarded_tools(session: Session) -> list[StructuredTool]:
    """
    Wrap every registered tool so it routes through execute_tool.

    This is the load-bearing function. Without it the agent runs with no
    budget, no business-rule validation, no idempotency and no approval gate —
    and nothing would look broken, because the tools themselves still work.

    StructuredTool.from_function takes the Pydantic model directly as
    args_schema, so the same schema drives the hand-built agent AND this one.
    One definition, no drift.
    """
    out = []
    for name, t in registry.REGISTRY.items():
        def runner(_name=name, **kwargs) -> str:
            # execute_tool does: schema validation -> guardrails -> execute.
            # Returning the error as a string rather than raising keeps the
            # same behaviour as the hand-built loop: the model SEES the refusal
            # and can correct, instead of the graph blowing up.
            return execute_tool(_name, kwargs, session)

        out.append(StructuredTool.from_function(
            func=runner,
            name=name,
            description=t.description,
            args_schema=t.args_model,
        ))
    return out


def build(session: Session):
    model = ChatAnthropic(
        model=MODEL,
        max_tokens=1024,
        temperature=TEMPERATURE,
        api_key=os.getenv("ANTHROPIC_API_KEY"),
    )
    # The one line that replaces the hand-built loop.
    #
    # Underneath it is a two-node graph: a "model" node that calls the LLM and
    # a "tools" node that executes any tool calls, with a conditional edge back
    # to the model node until the model stops requesting tools. Exactly the loop
    # in agent.py, expressed as a state machine. (The node was called "agent"
    # under the old prebuilt — renamed, like the parameters.)
    #
    # The prompt keyword is passed by name because the two API versions spell
    # it differently — see _PROMPT_KW above.
    return _create_agent(model, make_guarded_tools(session),
                         **{_PROMPT_KW: SYSTEM_PROMPT})


def run_langgraph(query: str, session: Session,
                  max_iterations: int = 8) -> tuple[str, list[dict]]:
    """
    Same signature as agent.run, so agent_eval can score either one.

    recursion_limit is LangGraph's iteration cap. It counts graph STEPS, not
    agent turns — each turn is roughly two steps (model node, then tools node),
    so the limit is doubled to stay comparable.
    """
    graph = build(session)
    result = graph.invoke(
        {"messages": [("user", query)]},
        config={"recursion_limit": max_iterations * 2},
    )

    messages = result["messages"]
    final = messages[-1].content
    if isinstance(final, list):   # content can be a list of blocks
        final = "".join(b.get("text", "") for b in final if isinstance(b, dict))

    # Rebuild a trace in the hand-built format, so the same eval works on both.
    #
    # Note how much is being RECONSTRUCTED here — the framework keeps its own
    # message objects and does not hand you the per-turn record agent.py built
    # as it went. Observability is a thing you add back.
    #
    # The token accounting below is the concrete example. agent.py accumulates
    # cost inside its loop straight off msg.usage, for free, because it sees
    # every response. Here the responses are buried in a message list and the
    # usage lives under a differently-named attribute (usage_metadata, a dict,
    # not msg.usage with int fields) — so the same number costs a post-hoc
    # walk over the messages plus a mapping between two shapes.
    #
    # The first version of this file skipped it and reported $0.0000 for a run
    # that plainly cost money. That is the failure mode worth remembering: the
    # framework did not break the metric loudly, it just stopped populating it,
    # and a zero in a cost column reads as "cheap" rather than "unmeasured".
    trace, turn = [], 0
    for m in messages:
        um = getattr(m, "usage_metadata", None) or {}
        tok_in = um.get("input_tokens", 0)
        tok_out = um.get("output_tokens", 0)
        cost = calculate_cost(MODEL, tok_in, tok_out)
        session.budget.usd_used += cost
        session.budget.tokens_used += tok_in + tok_out

        for call in getattr(m, "tool_calls", None) or []:
            trace.append({
                "turn": turn, "tool": call["name"], "args": call["args"],
                "result": "", "refused": False, "errored": False,
                "input_tokens": tok_in, "output_tokens": tok_out,
                "cost_usd": cost,
            })
            turn += 1

    last_um = getattr(messages[-1], "usage_metadata", None) or {}
    trace.append({
        "turn": turn, "tool": None, "args": None, "result": final,
        "refused": False, "errored": False,
        "input_tokens": last_um.get("input_tokens", 0),
        "output_tokens": last_um.get("output_tokens", 0),
        "cost_usd": calculate_cost(MODEL,
                                   last_um.get("input_tokens", 0),
                                   last_um.get("output_tokens", 0)),
    })
    return final, trace


def main():
    if len(sys.argv) < 2:
        print('usage: python langgraph_agent.py "your question"')
        sys.exit(1)

    session = Session(owner="rev", budget=Budget(max_tool_calls=8))
    final, trace = run_langgraph(" ".join(sys.argv[1:]), session)

    print(f"tools: {list(registry.REGISTRY)}\n")
    for t in trace:
        if t["tool"]:
            print(f"  [turn {t['turn']}] {t['tool']}({t['args']})")
    print(f"\n{final}")
    calls = sum(1 for t in trace if t["tool"])
    print(f"\n--- {calls} tool calls, "
          f"{session.budget.calls_used}/{session.budget.max_tool_calls} budget, "
          f"{session.budget.tokens_used} tokens, "
          f"${session.budget.usd_used:.4f} ---")


if __name__ == "__main__":
    main()
