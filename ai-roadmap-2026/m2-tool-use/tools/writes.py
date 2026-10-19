"""
tools/writes.py — the four tools that change something.

Built AFTER guardrails.py, deliberately. A save_application without an
idempotency key duplicates records on every retry, and a send_followup without
an approval gate eventually emails someone by accident. The protection has to
exist before the capability does.

    save_application   LOW_BLAST    reversible; idempotency key
    update_status      LOW_BLAST    reversible; legal-transition check
    draft_followup     READ_ONLY    produces text, touches nothing
    send_followup      HIGH_BLAST   reaches a real person; approval gate

Note draft_followup is READ_ONLY despite sounding like a write. Risk class is
about consequences, not verbs — writing a draft to the screen changes nothing.
Splitting draft from send is itself a safety decision: it gives the model
something useful to do that cannot hurt, and concentrates all the danger in one
tool you can guard heavily.
"""

from backend import ApplicationStore, BackendError, FixtureBackend
from schemas import (DraftFollowupArgs, SaveApplicationArgs, SendFollowupArgs,
                     UpdateStatusArgs)

from .registry import Tool, register

_jobs = FixtureBackend()
_store = ApplicationStore()


def _owner(ctx) -> str:
    return getattr(ctx, "owner", "rev") if ctx else "rev"


# ── save_application ──────────────────────────────────────────────────────────

def _save(args: SaveApplicationArgs, ctx) -> str:
    job = _jobs.get(args.job_id)          # existence already checked upstream
    idem = getattr(ctx, "extra", {}).get("idem_key")

    app = _store.save(job, _owner(ctx), args.notes, idem_key=idem)
    return (f"Saved {app.app_id}: {app.title} @ {app.company} "
            f"(status: {app.status.value})")


register(Tool(
    name="save_application",
    description=(
        "Save a job to the user's tracker so they can apply to it and track "
        "progress. Requires a job_id from search_jobs. Saving the same job "
        "twice is safe — it returns the existing record rather than "
        "duplicating."
    ),
    args_model=SaveApplicationArgs,
    fn=_save,
))


# ── update_status ─────────────────────────────────────────────────────────────

def _update(args: UpdateStatusArgs, ctx) -> str:
    # The legal-transition check already ran in validate_call. By the time a
    # tool executes, the call is known to be legal — tools do not re-check
    # policy, which keeps the rules in exactly one place.
    app = _store.update_status(args.app_id, _owner(ctx), args.new_status)
    return f"{app.app_id} ({app.title} @ {app.company}) is now '{app.status.value}'"


register(Tool(
    name="update_status",
    description=(
        "Move a saved application to a new status: saved, applied, screening, "
        "interviewing, offer, rejected, withdrawn. Only forward-progress "
        "transitions are allowed — a rejected application cannot be moved back "
        "to screening."
    ),
    args_model=UpdateStatusArgs,
    fn=_update,
))


# ── draft_followup ────────────────────────────────────────────────────────────

def _draft(args: DraftFollowupArgs, ctx) -> str:
    app = _store.get(args.app_id, _owner(ctx))
    days = (__import__("datetime").datetime.now() - app.updated_at).days

    # Deliberately a template rather than a model call. A tool that calls the
    # model from inside the agent loop is a second, hidden loop — it makes cost
    # and latency hard to attribute, and Week 4's trajectory eval would have no
    # visibility into it. If this needed real generation, the right shape is to
    # return the context and let the OUTER model write the text.
    return (
        f"Draft follow-up for {app.app_id} ({app.title} @ {app.company}, "
        f"status '{app.status.value}', last updated {days} days ago), "
        f"tone: {args.tone}\n\n"
        f"Subject: Following up — {app.title}\n\n"
        f"Hi,\n\nI wanted to follow up on my application for the "
        f"{app.title} role at {app.company}. I remain very interested and "
        f"would welcome the chance to discuss how my background fits the "
        f"team's needs.\n\nThanks for your time.\n"
    )


register(Tool(
    name="draft_followup",
    description=(
        "Write a draft follow-up message for a saved application. Returns text "
        "only — does NOT send anything. Use send_followup to actually send, "
        "which requires explicit user approval."
    ),
    args_model=DraftFollowupArgs,
    fn=_draft,
))


# ── send_followup ─────────────────────────────────────────────────────────────

def _send(args: SendFollowupArgs, ctx) -> str:
    """
    Reached ONLY after the approval gate returned without raising.

    Writes to outbox/ rather than wiring SMTP. The gate is the lesson; actually
    delivering mail adds real risk and teaches nothing extra. The agent can
    still be said to have "sent" it as far as the loop is concerned.
    """
    import datetime as dt
    from pathlib import Path

    app = _store.get(args.app_id, _owner(ctx))
    outbox = Path("outbox")
    outbox.mkdir(exist_ok=True)

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = outbox / f"{stamp}_{app.app_id}.txt"
    path.write_text(
        f"To: {app.company} (hiring contact)\n"
        f"Application: {app.app_id} — {app.title}\n"
        f"Subject: {args.subject}\n\n{args.body}\n"
    )
    return f"Approved and written to {path}. Review and send it yourself."


register(Tool(
    name="send_followup",
    description=(
        "Send a follow-up message for an application. REQUIRES EXPLICIT USER "
        "APPROVAL — the user is shown the full message and must confirm before "
        "anything is sent. Only use this when the user has clearly asked to "
        "send, not merely to draft."
    ),
    args_model=SendFollowupArgs,
    fn=_send,
))
