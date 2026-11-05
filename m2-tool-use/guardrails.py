"""
guardrails.py — Month 2, Week 3

WHAT      The safety layer. Protection proportional to what a tool can damage.
EXPORTS   RiskClass, TOOL_RISK, Session, Budget, apply_guardrails(),
          idempotency_key(), validate_call(), require_approval()
          Exceptions: GuardrailViolation, ApprovalDenied, BudgetExceeded
CALLED BY agent.execute_tool, in this order:
          budget -> business rules -> idempotency (writes) -> approval (high-blast)

══════════════════════════ reasoning and notes below ══════════════════════════

THE CORE IDEA
-------------
A bad search costs a fraction of a cent. A bad follow-up email reaches a hiring
manager and cannot be recalled. Applying the same guardrails to both is either
too strict for the search or too loose for the email.

So every tool declares a RISK CLASS, and the executor applies the guardrails
that class requires:

  READ_ONLY      external data, no side effects        validation only
  SCOPED_READ    YOUR data                             + server-side scope
  LOW_BLAST      write, reversible                     + idempotency, audit log
  HIGH_BLAST     write, irreversible, reaches a human  + approval gate, cap

Proof you understand this, and the stated closure criterion for the Q2
interview gap: given an arbitrary tool set, classify it and name the guardrail
each class needs.

DISPATCH ORDER IS NOT ARBITRARY
-------------------------------
budget -> business rules -> idempotency -> approval.

Budget first because it is the cheapest check and the only one that should stop
a runaway loop regardless of what the call is. Approval last because it is the
only one that costs a human's attention — never interrupt someone to approve a
call that was going to fail validation anyway.
"""

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum


class RiskClass(str, Enum):
    READ_ONLY = "read_only"
    SCOPED_READ = "scoped_read"
    LOW_BLAST = "low_blast"
    HIGH_BLAST = "high_blast"


# Which tool is which. Deliberately explicit rather than inferred from the name —
# you want this list reviewable at a glance.
TOOL_RISK: dict[str, RiskClass] = {
    "search_jobs":        RiskClass.READ_ONLY,
    "get_job_details":    RiskClass.READ_ONLY,
    "list_applications":  RiskClass.SCOPED_READ,
    "save_application":   RiskClass.LOW_BLAST,
    "update_status":      RiskClass.LOW_BLAST,
    "draft_followup":     RiskClass.READ_ONLY,   # produces text, touches nothing
    "send_followup":      RiskClass.HIGH_BLAST,

    # Aliases for the Week 2 routing experiment, which renames tools to
    # tool_a/b/c to neutralise the signal their names carry. Risk class is a
    # property of what a tool DOES, so the alias inherits it unchanged.
    "tool_a":             RiskClass.READ_ONLY,    # search_jobs
    "tool_b":             RiskClass.READ_ONLY,    # get_job_details
    "tool_c":             RiskClass.SCOPED_READ,  # list_applications
}


class GuardrailViolation(Exception):
    """Raised when a proposed tool call is refused. The message goes back to the
    model as a tool_result error, so it can correct itself — same bounded
    self-correction pattern as Month 1's retry loop."""


# ── Budgets ───────────────────────────────────────────────────────────────────

@dataclass
class Budget:
    """
    Per-session caps. The backstop for when every other guardrail is bypassed.

    Uncapped agents are how people wake up to a four-figure bill: the model gets
    stuck, re-calls the same tool with near-identical arguments, and nothing
    stops it.
    """
    max_tool_calls: int = 20
    max_tokens: int = 100_000
    max_usd: float = 1.00
    max_high_blast: int = 3          # sending 20 follow-ups is never right

    calls_used: int = 0
    tokens_used: int = 0
    usd_used: float = 0.0
    high_blast_used: int = 0

    def check(self, risk: RiskClass):
        if self.calls_used >= self.max_tool_calls:
            raise GuardrailViolation(
                f"tool call budget exhausted ({self.max_tool_calls})")
        if self.usd_used >= self.max_usd:
            raise GuardrailViolation(f"spend cap reached (${self.max_usd})")
        if risk is RiskClass.HIGH_BLAST and self.high_blast_used >= self.max_high_blast:
            raise GuardrailViolation(
                f"high-blast action cap reached ({self.max_high_blast})")

    def record(self, risk: RiskClass, tokens: int = 0, usd: float = 0.0):
        self.calls_used += 1
        self.tokens_used += tokens
        self.usd_used += usd
        if risk is RiskClass.HIGH_BLAST:
            self.high_blast_used += 1


# ── Server-side parameters ────────────────────────────────────────────────────

@dataclass
class Session:
    """
    Trusted state. Anything derivable from here must NEVER be model-filled.

    The single highest-value guardrail in the whole file: if the model can set
    `owner`, a crafted prompt can read another user's applications. Injecting it
    server-side deletes that vulnerability class rather than guarding against it.

    Server-side parameters travel on the SESSION, not in the arguments. An
    earlier version injected `owner` into the args dict and re-validated, which
    `extra="forbid"` rejected — the guardrail fighting its own schema, and a
    sign the parameter was in the wrong channel.
    """
    owner: str
    budget: Budget = field(default_factory=Budget)
    # Per-call context from the guardrails — currently the idempotency key.
    # Set by apply_guardrails, read by whichever tool is about to run.
    extra: dict = field(default_factory=dict)


def inject_server_params(tool_name: str, args: dict, session: Session) -> dict:
    """
    Add trusted parameters the model was never allowed to supply.

    Note this runs AFTER schema validation, and the argument models deliberately
    omit these fields — so a model attempting to pass `owner` is rejected by
    `extra="forbid"` before reaching here.
    """
    args = dict(args)
    if tool_name in ("list_applications", "save_application",
                     "update_status", "draft_followup", "send_followup"):
        args["owner"] = session.owner
    return args


# ── Idempotency ───────────────────────────────────────────────────────────────

def idempotency_key(session: Session, tool_name: str, args: dict) -> str:
    """
    Stable id for one logical operation, so a retry does not save the same
    application twice.

    Server-generated, always. A model-generated key would differ on the retry
    and silently defeat the whole mechanism.
    """
    payload = json.dumps({"o": session.owner, "t": tool_name,
                          "a": {k: args[k] for k in sorted(args)}},
                         sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ── Argument validation beyond the schema ─────────────────────────────────────

def validate_call(tool_name: str, args: dict, session: "Session") -> None:
    """
    Business rules Pydantic structurally cannot check.

    A schema validates one call in isolation: types, ranges, formats. It cannot
    see stored state, so it cannot know that `rejected -> screening` is not a
    real transition, or that job_id "j_999" does not exist.

    That distinction is worth being precise about in an interview:

        schema validation      is this call WELL-FORMED?
        business validation    is this call LEGAL, given the current state?

    Anything a prompt can request, a prompt injection can also request — so
    these checks live in code, never in the system prompt.

    Raises GuardrailViolation with a message specific enough that the model can
    correct itself on the next turn.
    """
    from backend import ApplicationStore, BackendError, FixtureBackend
    from schemas import LEGAL_TRANSITIONS, AppStatus

    owner = session.owner

    if tool_name == "save_application":
        try:
            FixtureBackend().get(args["job_id"])
        except BackendError:
            raise GuardrailViolation(
                f"no job with id {args['job_id']!r}. "
                f"Call search_jobs first to get a valid job_id.")

    elif tool_name == "update_status":
        try:
            app = ApplicationStore().get(args["app_id"], owner)
        except BackendError as e:
            raise GuardrailViolation(str(e))

        new = AppStatus(args["new_status"])
        allowed = LEGAL_TRANSITIONS[app.status]
        if new not in allowed:
            # The error names the legal options, so a correction is possible
            # rather than a guess. Bounded self-correction needs actionable
            # errors — same lesson as Month 1's retry loop.
            legal = ", ".join(sorted(s.value for s in allowed)) or "none (terminal)"
            raise GuardrailViolation(
                f"cannot move {app.app_id} from '{app.status.value}' to "
                f"'{new.value}'. Legal transitions from "
                f"'{app.status.value}': {legal}")

    elif tool_name in ("draft_followup", "send_followup"):
        try:
            app = ApplicationStore().get(args["app_id"], owner)
        except BackendError as e:
            raise GuardrailViolation(str(e))

        # Following up on a closed application is a mistake the model will
        # otherwise make happily, and an embarrassing one to send.
        if app.status in (AppStatus.REJECTED, AppStatus.WITHDRAWN):
            raise GuardrailViolation(
                f"{app.app_id} is '{app.status.value}' — a follow-up is not "
                f"appropriate for a closed application.")


# ── The approval gate ─────────────────────────────────────────────────────────

class ApprovalDenied(GuardrailViolation):
    """The human declined. Distinct from a rule violation — nothing was wrong
    with the call, it just wasn't wanted. The eval counts them separately."""


def require_approval(tool_name: str, args: dict, session: "Session",
                     auto: bool | None = None) -> None:
    """
    HIGH_BLAST actions emit a PROPOSAL and stop. They do not act.

    Prints the full content and requires a typed confirmation — not Enter,
    which people hit reflexively.

    `auto` exists only for tests: True simulates approval, False simulates
    denial. It is never set from anything the model produces, which is the
    property that makes the gate structural rather than advisory.

    THE TEST THAT MATTERS: is there any sequence of model outputs that results
    in a send without a human keystroke? If yes, the gate is decoration.
    """
    if auto is not None:
        if not auto:
            raise ApprovalDenied(f"{tool_name} was declined by the user")
        return

    print(f"\n{'!'*70}")
    print(f"APPROVAL REQUIRED — {tool_name}")
    print(f"{'!'*70}")
    for k, v in args.items():
        if k == "owner":
            continue
        print(f"\n{k}:\n{v}")
    print(f"\n{'!'*70}")

    reply = input("Type SEND to confirm, anything else to cancel: ").strip()
    if reply != "SEND":
        raise ApprovalDenied(f"{tool_name} cancelled (typed {reply!r})")


# ── Dispatch ──────────────────────────────────────────────────────────────────

def apply_guardrails(tool_name: str, args: dict, session: Session,
                     auto_approve: bool | None = None) -> dict:
    """
    Run every guardrail this tool's risk class requires, in increasing order of
    cost — cheap checks first, so an expensive one never runs for a call that
    was going to be refused anyway.

    Returns extra context for the tool (currently the idempotency key, where
    one applies). Raises GuardrailViolation if the call is refused.

    THE DISPATCH IS THE POINT. Every tool gets validation; only writes get
    idempotency; only high-blast gets a human. Protection proportional to what
    the call can damage — uniform guardrails are too strict for a search and
    too loose for an email.
    """
    risk = TOOL_RISK.get(tool_name)
    if risk is None:
        raise GuardrailViolation(f"unknown tool {tool_name!r}")

    extra: dict = {}

    # 1. BUDGET — cheapest check, and it applies to everything.
    session.budget.check(risk)

    # 2. BUSINESS RULES — all classes. Reads can be invalid too ("show me
    #    app_999"), and a clear refusal beats a confusing empty result.
    validate_call(tool_name, args, session)

    # 3. IDEMPOTENCY — writes only. A retry must not create a second record.
    if risk in (RiskClass.LOW_BLAST, RiskClass.HIGH_BLAST):
        extra["idem_key"] = idempotency_key(session, tool_name, args)

    # 4. HUMAN APPROVAL — high blast only. Last, because it is the only step
    #    that costs a person's attention, and it should never be spent on a
    #    call that a cheaper check would have refused.
    if risk is RiskClass.HIGH_BLAST:
        require_approval(tool_name, args, session, auto=auto_approve)

    return extra
