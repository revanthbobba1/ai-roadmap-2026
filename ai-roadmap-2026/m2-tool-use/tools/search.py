"""
tools/search.py — the worked example.

One tool, complete, so the shape is clear. Every other tool follows this
pattern: a description, an argument model, a function, and a register() call.

ON THE DESCRIPTION
------------------
The version below is deliberately written to be *separable* — it says what this
tool does and, just as importantly, what it does NOT do.

Week 2 Day 1-2 asks you to first write it badly on purpose. Something like
"Find job information" overlaps with get_job_details and list_applications, and
the model will misroute. Measure that rate, then fix the descriptions and
measure again. That delta is the experiment.
"""

from backend import FixtureBackend
from schemas import SearchJobsArgs

from .registry import Tool, register

_backend = FixtureBackend()


def _run(args: SearchJobsArgs, ctx) -> str:
    """
    Execute the search and return a string for the model.

    Returning a compact summary rather than the full records is deliberate:
    every tool result is appended to the conversation and paid for on every
    subsequent turn. Context growth is the thing that makes multi-turn agents
    expensive non-linearly, and it starts here.
    """
    jobs = _backend.search(args.query, args.location, args.max_results)
    if not jobs:
        return "No matching jobs found."

    lines = [f"Found {len(jobs)} jobs:"]
    for j in jobs:
        pay = ""
        if j.salary_min and j.salary_max:
            pay = f" | ${j.salary_min:,}-${j.salary_max:,}"
        lines.append(f"  {j.job_id} | {j.title} @ {j.company} | {j.location}{pay}")
    lines.append("Use get_job_details(job_id) for the full description.")
    return "\n".join(lines)


register(Tool(
    name="search_jobs",
    description=(
        "Search external job postings. Returns a short list of matches with "
        "id, title, company, location and salary range. Use this to DISCOVER "
        "jobs that are new to the user. Omit `query` to list everything "
        "available in a location. Does not return full descriptions, and does "
        "not search jobs the user has already saved — use list_applications "
        "for those."
    ),
    args_model=SearchJobsArgs,
    fn=_run,
))
