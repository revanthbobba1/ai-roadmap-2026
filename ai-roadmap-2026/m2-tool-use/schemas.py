"""
schemas.py — Month 2

Pydantic models for tool arguments and stored records.

Same single-source-of-truth pattern as Month 1: each tool's argument model
generates the JSON Schema handed to the provider AND validates what comes back.
A hand-written tool schema that disagrees with your validator is a bug that only
shows up in production.

Two kinds of model live here:
  - ARGUMENT models  what a tool accepts. These become tool schemas.
  - RECORD models    what gets stored. These never reach the model.
"""

import datetime as _dt
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ── Status, and the transitions that are legal ────────────────────────────────

class AppStatus(str, Enum):
    SAVED = "saved"
    APPLIED = "applied"
    SCREENING = "screening"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


# Not every status change makes sense. You cannot go from `rejected` back to
# `screening`. Week 3 enforces this in update_status — a business rule the
# schema alone cannot express, which is exactly the kind of check that belongs
# in code rather than in the prompt.
LEGAL_TRANSITIONS: dict[AppStatus, set[AppStatus]] = {
    AppStatus.SAVED:        {AppStatus.APPLIED, AppStatus.WITHDRAWN},
    AppStatus.APPLIED:      {AppStatus.SCREENING, AppStatus.REJECTED, AppStatus.WITHDRAWN},
    AppStatus.SCREENING:    {AppStatus.INTERVIEWING, AppStatus.REJECTED, AppStatus.WITHDRAWN},
    AppStatus.INTERVIEWING: {AppStatus.OFFER, AppStatus.REJECTED, AppStatus.WITHDRAWN},
    AppStatus.OFFER:        {AppStatus.REJECTED, AppStatus.WITHDRAWN},
    AppStatus.REJECTED:     set(),
    AppStatus.WITHDRAWN:    set(),
}


# ── Records (stored; never sent to the model as a schema) ─────────────────────

class Job(BaseModel):
    job_id: str
    title: str
    company: str
    location: str
    posted: _dt.date | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    description: str = ""
    url: str | None = None


class Application(BaseModel):
    app_id: str
    job_id: str
    title: str
    company: str
    status: AppStatus = AppStatus.SAVED
    notes: str = ""
    saved_at: _dt.datetime
    updated_at: _dt.datetime
    # Set server-side from the session, never by the model. See guardrails.py.
    owner: str


# ── Tool argument models (these become the tool schemas) ──────────────────────
#
# Field descriptions matter more than you'd expect. The model reads them when
# deciding what to put in each slot, so a vague description produces a
# right-tool-wrong-arguments failure — which Week 2 measures separately from
# wrong-tool failures, because the fixes differ.

class SearchJobsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")   # reject unknown fields outright

    # `query` was originally REQUIRED, which caused a real failure worth
    # recording. Asked "which Boston job pays best?" — a question naming no
    # role — the model was forced to supply something and sent query="job",
    # which matched nothing. Right tool, wrong argument, and the schema left it
    # no good option.
    #
    # A required field the caller cannot always sensibly fill is a schema bug,
    # not a model bug. Making it optional is the fix; the description then has
    # to say what omitting it means.
    query: str | None = Field(
        default=None,
        description=("Job title or keywords, e.g. 'backend engineer'. "
                     "OMIT THIS to list all jobs — do not pass a generic word "
                     "like 'job' or 'any'."))
    location: str | None = Field(
        default=None, description="City or region. Omit for remote/anywhere.")
    max_results: int = Field(default=10, ge=1, le=50)


class GetJobDetailsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(description="The job_id returned by search_jobs")


class ListApplicationsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # NOTE there is no `owner` field here, deliberately. It is injected
    # server-side from the session. If the model could set it, a crafted prompt
    # could read someone else's applications.
    status: AppStatus | None = Field(
        default=None, description="Filter to one status. Omit for all.")


class SaveApplicationArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(description="The job_id to save")
    notes: str = Field(default="", description="Why this one is worth pursuing")


class UpdateStatusArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: str = Field(description="The application to update")
    new_status: AppStatus = Field(description="The status to move it to")


class DraftFollowupArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: str = Field(description="The application to write a follow-up about")
    tone: str = Field(default="professional",
                      description="e.g. professional, warm, brief")


class SendFollowupArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: str
    subject: str
    body: str
    # No recipient field. The address comes from the stored application record,
    # not from the model — same reasoning as `owner` above.
