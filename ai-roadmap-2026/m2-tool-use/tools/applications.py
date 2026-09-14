"""
tools/applications.py — list_applications

The first SCOPED_READ tool: it reads your data rather than public job postings.

WHY THAT MATTERS
----------------
ListApplicationsArgs has no `owner` field, deliberately. The owner is injected
server-side from the session (guardrails.inject_server_params), so the model has
no way to request someone else's applications — there is no slot for it to fill.

Contrast with validating an owner the model supplied: that guards the
vulnerability. Removing the parameter deletes it. Same distinction that cost
points on the Q2 mock.

Week 3 tests this adversarially: craft an input trying to read another user's
data and confirm it is impossible rather than merely discouraged.
"""

from backend import ApplicationStore
from schemas import ListApplicationsArgs

from .registry import Tool, register

_store = ApplicationStore()


def _run(args: ListApplicationsArgs, ctx) -> str:
    # `owner` arrives via guardrails, not via args — which is why it is read
    # off the session here rather than off the validated arguments.
    owner = getattr(ctx, "owner", "rev") if ctx else "rev"

    apps = _store.list(owner, args.status)
    if not apps:
        scope = f" with status '{args.status.value}'" if args.status else ""
        return f"No saved applications{scope}."

    lines = [f"{len(apps)} application(s):"]
    for a in apps:
        lines.append(
            f"  {a.app_id} | {a.title} @ {a.company} | {a.status.value} "
            f"| saved {a.saved_at:%Y-%m-%d}"
            + (f" | {a.notes}" if a.notes else "")
        )
    return "\n".join(lines)


register(Tool(
    name="list_applications",
    description=(
        "List jobs the user has ALREADY SAVED to their tracker, optionally "
        "filtered by status. Use this for questions about what the user has "
        "applied to or is tracking. Does not search for new jobs — use "
        "search_jobs for that."
    ),
    args_model=ListApplicationsArgs,
    fn=_run,
))
