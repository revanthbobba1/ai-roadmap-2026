"""
guardrails.py — Month 2, Week 3

Protection proportional to what a tool can damage.

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

WHAT IS BUILT HERE vs. WHAT YOU BUILD
-------------------------------------
The risk enum, the registry of which tool is which class, and the dispatch
skeleton are done. The individual guardrails are Week 3's work and are marked
TODO with the reasoning attached.
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
    """
    owner: str
    budget: Budget = field(default_factory=Budget)


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


# ── TODO Week 3 Day 3-4: argument validation beyond the schema ────────────────
#
# Pydantic checks types and ranges. It cannot check business rules that depend
# on stored state. Build:
#
#   def validate_call(tool_name, args, backend) -> None:
#       - update_status: is this transition in LEGAL_TRANSITIONS?
#         (schemas.py defines the table; rejecting rejected -> screening is here)
#       - save_application: does job_id actually exist?
#       - send_followup: does the application exist, and is it in a status where
#         a follow-up makes sense? Following up on a rejection is a mistake the
#         model will happily make.
#
# Raise GuardrailViolation with a message specific enough that the model can
# correct itself on the next turn.


# ── TODO Week 3 Day 5-6: the approval gate ────────────────────────────────────
#
# def require_approval(tool_name: str, args: dict) -> bool:
#     """
#     HIGH_BLAST actions emit a PROPOSAL, not an action.
#
#     Print the recipient, subject, and full body. Require an explicit typed
#     confirmation — not just Enter, which people hit reflexively.
#
#     Strong suggestion: do not wire real SMTP. Write the approved email to
#     outbox/ for you to send by hand. The gate is the lesson; actually
#     delivering mail adds risk and teaches nothing extra.
#     """
#
# The property worth testing: with the gate in place, is there ANY sequence of
# model outputs that results in a sent email without your keystroke? If yes, the
# gate is advisory rather than structural, and structural is the point.


# ── Dispatch ──────────────────────────────────────────────────────────────────

def apply_guardrails(tool_name: str, args: dict, session: Session) -> dict:
    """
    Run every guardrail required by this tool's risk class.
    Returns the arguments to actually execute with.
    Raises GuardrailViolation if the call is refused.
    """
    risk = TOOL_RISK.get(tool_name)
    if risk is None:
        raise GuardrailViolation(f"unknown tool {tool_name!r}")

    session.budget.check(risk)
    args = inject_server_params(tool_name, args, session)

    # TODO Week 3: validate_call(tool_name, args, backend)
    # TODO Week 3: if risk is LOW_BLAST -> attach idempotency_key(...)
    # TODO Week 3: if risk is HIGH_BLAST -> require_approval(...) or refuse

    return args
