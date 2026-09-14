"""
tools/job_details.py — get_job_details

The second read tool, and the one that makes CHAINING possible. search_jobs
returns ids; this turns an id into a full description. The model cannot know
which id to ask about until the search comes back, so a question like "which of
these mentions Java?" genuinely requires two sequential turns.

That is the thing multi-turn agents are for, and a single-tool agent can't
demonstrate it.
"""

from backend import BackendError, FixtureBackend
from schemas import GetJobDetailsArgs

from .registry import Tool, register

_backend = FixtureBackend()


def _run(args: GetJobDetailsArgs, ctx) -> str:
    try:
        j = _backend.get(args.job_id)
    except BackendError as e:
        # Returned as text, not raised. The model sees the failure and can
        # correct — usually by re-running search_jobs to get a valid id.
        return f"ERROR: {e}"

    pay = (f"${j.salary_min:,}-${j.salary_max:,}"
           if j.salary_min and j.salary_max else "not stated")
    return (
        f"{j.title} @ {j.company}\n"
        f"Location: {j.location}\n"
        f"Salary: {pay}\n"
        f"Posted: {j.posted}\n"
        f"URL: {j.url}\n\n"
        f"{j.description}"
    )


register(Tool(
    name="get_job_details",
    description=(
        "Get the full description of ONE job posting, given a job_id from "
        "search_jobs. Returns requirements, responsibilities and salary in "
        "full. Use this when the user asks about a specific role's details or "
        "requirements. Does not search — you need a job_id first."
    ),
    args_model=GetJobDetailsArgs,
    fn=_run,
))
