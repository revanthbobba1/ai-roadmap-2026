"""
workflow.py — Month 2, Week 6

WHAT      The same questions answered by a FIXED pipeline instead of an agent.
          Always retrieve, then answer. The model never chooses a tool.
EXPORTS   run_workflow(query, session, max_iterations=None) -> (final, trace)
          Same signature as agent.run, so agent_eval scores it too.
COMPARE   python agent_eval.py 5 workflow

══════════════════════════ reasoning and notes below ══════════════════════════

WHY BUILD THE THING YOU ALREADY REPLACED
----------------------------------------
"When would you NOT build an agent?" is a standard interview question and almost
nobody answers it with numbers. This produces the numbers.

An agent's defining feature is that the model decides whether to call a tool and
which one. That decision is not free:

  - it costs a round trip per decision
  - it introduces variance, because the decision can differ between runs
  - it can go wrong in ways a fixed path cannot

A workflow gives all of that up and gets determinism in exchange. The question
is what the exchange is worth, which depends entirely on how well the fixed path
fits the question being asked.

THE SHAPE
---------
    question
      |
      +-- LLM call 1   extract search arguments (FORCED tool call)
      +-- search_jobs                          (deterministic)
      +-- get_job_details x N                  (deterministic loop)
      +-- LLM call 2   answer from what was retrieved

Exactly two LLM calls, every time, whatever the question. Compare with the
agent: 2 calls for a simple lookup, 4 for a chained one, and it decides which.

NOTE WHAT "FORCED TOOL CALL" MEANS HERE
---------------------------------------
Call 1 passes tool_choice={"type": "tool", "name": "search_jobs"}, so the model
must emit a search_jobs call. It is being used purely as a parameter extractor —
turning "which Boston job pays most?" into {"location": "Boston"}. It has no say
in WHETHER to search or WHICH tool to use. That is the line between a workflow
and an agent, and it is one keyword wide.

This is also exactly the shape of naive RAG: retrieve unconditionally, stuff the
results into context, generate. Month 3 is this pipeline with documents instead
of job postings, which is why the comparison is worth having now.

WHAT THIS PIPELINE CANNOT DO, BY CONSTRUCTION
---------------------------------------------
Predictions to check against the eval rather than assert:

  e03   "what am I tracking?" needs list_applications. The pipeline only ever
        searches external postings, so it answers from the wrong data source.
  e07-09 cover-letter and timing advice need no tool at all. The pipeline
        retrieves anyway: wasted calls, and job ids may leak into the answer.
  e10-12 the should_refuse cases.

That last group is the interesting one. The pipeline cannot send an email or
apply to anything because those tools are not wired into it. It is safe, but not
because it decided to be — the capability simply is not there.

  > In a workflow, blast radius is a design-time property.
  > In an agent, it is a runtime one.

Which is a real argument for workflows wherever the task permits one. A tool the
pipeline never calls needs no approval gate, because there is no path to it.

Run:  python workflow.py "which Boston job pays the most?"
"""

import os
import re
import sys

import anthropic
from dotenv import load_dotenv

import tools  # noqa: F401 — registers them
from agent import MODEL, TEMPERATURE, execute_tool
from guardrails import Budget, Session
from llm_client import calculate_cost
from tools import registry

load_dotenv(override=True)

# How many postings to fetch full details for. Fixed, not chosen.
#
# This is the central trade in one constant. The agent fetches details for
# exactly the jobs it needs — usually one. The pipeline cannot know which, so it
# either over-fetches (wasted calls on every request) or under-fetches (misses
# the one that mattered). 3 is a guess that cannot be right for every question,
# and having to guess at all is the cost of removing the decision.
DETAIL_TOP_N = 3

EXTRACT_PROMPT = """Extract search parameters from the user's question.

Use the location if one is mentioned. Omit `query` unless the question names a
specific role or skill — do not pass a generic word like "job".

Question: {query}"""

ANSWER_PROMPT = """Answer the user's question using only the job postings below.

If the postings do not contain what the question asks about, say so plainly
rather than guessing.

QUESTION
{query}

JOB POSTINGS
{context}"""

# Matches the id at the start of a search_jobs result line:
#   "  j_004 | Machine Learning Engineer @ Corvid Labs | Boston | $175,000-..."
JOB_ID_RE = re.compile(r"^\s*(j_\d+)\s*\|", re.MULTILINE)


def _call(client, session, system, user, **kw) -> anthropic.types.Message:
    """One API call, with cost recorded onto the session.

    Recorded here rather than in execute_tool because execute_tool only knows
    about tool calls. Keeping the accounting in one place is what makes the
    cost column comparable across all three implementations.
    """
    msg = client.messages.create(
        model=MODEL, max_tokens=1024, system=system,
        messages=[{"role": "user", "content": user}],
        extra_body={"temperature": TEMPERATURE},
        **kw,
    )
    session.budget.usd_used += calculate_cost(
        MODEL, msg.usage.input_tokens, msg.usage.output_tokens)
    session.budget.tokens_used += msg.usage.input_tokens + msg.usage.output_tokens
    return msg


def run_workflow(query: str, session: Session,
                 max_iterations: int | None = None) -> tuple[str, list[dict]]:
    """
    Fixed pipeline. max_iterations is accepted and ignored — there is no loop to
    cap, which is itself part of the comparison. A workflow cannot run away.
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    trace, turn = [], 0

    # ── Step 1: extract search arguments ─────────────────────────────────────
    # tool_choice forces a search_jobs call. The model fills the parameters; it
    # does not get to pick the tool or decline to search.
    spec = [t for t in registry.specs("claude") if t["name"] == "search_jobs"]
    msg = _call(
        client, session,
        system="You extract structured search parameters. Call the tool.",
        user=EXTRACT_PROMPT.format(query=query),
        tools=spec,
        tool_choice={"type": "tool", "name": "search_jobs"},
    )
    blocks = [b for b in msg.content if b.type == "tool_use"]
    raw_args = blocks[0].input if blocks else {}

    # ── Step 2: search, always ───────────────────────────────────────────────
    # Through execute_tool, so validation, guardrails and the budget counter
    # behave identically to the agent. Only the decision-making is removed.
    search_result = execute_tool("search_jobs", raw_args, session)
    trace.append({
        "turn": turn, "tool": "search_jobs", "args": raw_args,
        "result": search_result, "refused": False, "errored": False,
        "input_tokens": msg.usage.input_tokens,
        "output_tokens": msg.usage.output_tokens, "cost_usd": 0.0,
    })
    turn += 1

    # ── Step 3: fetch details for the top N, always ──────────────────────────
    context = [search_result]
    for job_id in JOB_ID_RE.findall(search_result)[:DETAIL_TOP_N]:
        detail = execute_tool("get_job_details", {"job_id": job_id}, session)
        context.append(detail)
        trace.append({
            "turn": turn, "tool": "get_job_details", "args": {"job_id": job_id},
            "result": detail, "refused": False, "errored": False,
            "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
        })
        turn += 1

    # ── Step 4: answer from what was retrieved ───────────────────────────────
    final_msg = _call(
        client, session,
        system="You are a job application assistant.",
        user=ANSWER_PROMPT.format(query=query, context="\n\n---\n\n".join(context)),
    )
    final = "".join(b.text for b in final_msg.content if b.type == "text")

    trace.append({
        "turn": turn, "tool": None, "args": None, "result": final,
        "refused": False, "errored": False,
        "input_tokens": final_msg.usage.input_tokens,
        "output_tokens": final_msg.usage.output_tokens,
        "cost_usd": 0.0,
    })
    return final, trace


def main():
    if len(sys.argv) < 2:
        print('usage: python workflow.py "your question"')
        sys.exit(1)

    session = Session(owner="rev", budget=Budget(max_tool_calls=8))
    final, trace = run_workflow(" ".join(sys.argv[1:]), session)

    for t in trace:
        if t["tool"]:
            print(f"  [step {t['turn']}] {t['tool']}({t['args']})")
    print(f"\n{final}")
    calls = sum(1 for t in trace if t["tool"])
    print(f"\n--- 2 LLM calls (always), {calls} tool calls, "
          f"{session.budget.tokens_used} tokens, "
          f"${session.budget.usd_used:.4f} ---")


if __name__ == "__main__":
    main()
