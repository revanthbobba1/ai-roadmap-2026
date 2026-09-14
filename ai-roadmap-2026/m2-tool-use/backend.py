"""
backend.py — Month 2

Where data actually lives. Two implementations behind one interface:

  FixtureBackend   reads recorded job postings from fixtures/jobs.json
  LiveBackend      hits a real job-search API            (Week 5)

WHY BOTH — record and replay
----------------------------
Live APIs return different data every day. A trajectory test recorded today
fails tomorrow because the job listings changed, not because your agent got
worse. That is a flaky test, and flaky tests get ignored.

So: fixtures for the eval suite, live API for daily use. Weeks 1-4 run entirely
on fixtures so results are reproducible; Week 5 swaps in the live source behind
the same interface and the eval keeps running against the recordings.

This is a real production pattern (VCR cassettes, golden files), not a shortcut
for a learning project.

Applications are stored in applications.json — that is YOUR data and it persists
either way.
"""

import datetime as _dt
import json
import uuid
from pathlib import Path

from schemas import Application, AppStatus, Job

FIXTURES = Path("fixtures/jobs.json")
STORE = Path("applications.json")


class BackendError(Exception):
    """Tool-level failure — the job doesn't exist, the store is unreadable.

    Distinct from GuardrailViolation (the call was refused) because the eval
    attributes them differently: a guardrail refusal is the system working, a
    backend error is the tool itself failing.
    """


# ── Jobs (read) ───────────────────────────────────────────────────────────────

class FixtureBackend:
    """Recorded job postings. Deterministic, which is what the eval needs."""

    def __init__(self, path: Path = FIXTURES):
        self.path = path
        self._jobs: list[Job] | None = None

    @property
    def jobs(self) -> list[Job]:
        if self._jobs is None:
            if not self.path.exists():
                raise BackendError(f"fixtures not found at {self.path}")
            self._jobs = [Job.model_validate(j) for j in
                          json.loads(self.path.read_text())]
        return self._jobs

    def search(self, query: str | None = None, location: str | None = None,
               max_results: int = 10) -> list[Job]:
        """
        Naive AND-matching over title + company + description.

        Deliberately crude — a real search engine is not what this month is
        about. But know its limits when writing eval cases: it has no stemming,
        no synonyms, and no relevance ranking, so "engineer" matches 4 jobs
        while "engineers" matches none. Do not build a test around a match this
        happens to produce.

        query=None returns everything (subject to the location filter), which is
        the correct behaviour for "what's available in Boston?"
        """
        out = []
        for j in self.jobs:
            if query:
                hay = f"{j.title} {j.company} {j.description}".lower()
                if not all(w in hay for w in query.lower().split()):
                    continue
            if location and location.lower() not in j.location.lower():
                continue
            out.append(j)
        return out[:max_results]

    def get(self, job_id: str) -> Job:
        for j in self.jobs:
            if j.job_id == job_id:
                return j
        raise BackendError(f"no job with id {job_id!r}")


# ── TODO Week 5: LiveBackend ──────────────────────────────────────────────────
#
# class LiveBackend:
#     """Same two methods, hitting a real API. Adzuna has a free developer tier.
#
#     Two things to build alongside it:
#       1. a `record=True` mode that appends responses to fixtures/ — so your
#          eval set grows from real data rather than invented data
#       2. a response cache, because search_jobs is read-only and re-querying
#          the same thing within a session is waste
#     """


# ── Applications (your data, read + write) ────────────────────────────────────

class ApplicationStore:
    """
    Flat JSON file. A database would be more correct and would teach nothing
    this month is about — the interesting problems here are guardrails and
    evaluation, not persistence.
    """

    def __init__(self, path: Path = STORE):
        self.path = path

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text())

    def _save(self, rows: list[dict]):
        self.path.write_text(json.dumps(rows, indent=2, default=str) + "\n")

    def list(self, owner: str, status: AppStatus | None = None) -> list[Application]:
        rows = [Application.model_validate(r) for r in self._load()]
        # The owner filter is the whole point of SCOPED_READ. `owner` arrives
        # from the session, never from the model.
        rows = [a for a in rows if a.owner == owner]
        if status is not None:
            rows = [a for a in rows if a.status == status]
        return rows

    def get(self, app_id: str, owner: str) -> Application:
        for a in self.list(owner):
            if a.app_id == app_id:
                return a
        raise BackendError(f"no application {app_id!r}")

    def save(self, job: Job, owner: str, notes: str = "",
             idem_key: str | None = None) -> Application:
        """
        Create an application record.

        idem_key is how a retry avoids creating a duplicate. Week 3 wires it in;
        the check is here so the storage layer enforces it rather than trusting
        the caller.
        """
        rows = self._load()
        if idem_key and any(r.get("idem_key") == idem_key for r in rows):
            existing = next(r for r in rows if r.get("idem_key") == idem_key)
            return Application.model_validate(existing)

        now = _dt.datetime.now()
        app = Application(
            app_id=f"app_{uuid.uuid4().hex[:8]}",
            job_id=job.job_id, title=job.title, company=job.company,
            status=AppStatus.SAVED, notes=notes,
            saved_at=now, updated_at=now, owner=owner,
        )
        row = json.loads(app.model_dump_json())
        if idem_key:
            row["idem_key"] = idem_key
        rows.append(row)
        self._save(rows)
        return app

    def update_status(self, app_id: str, owner: str,
                      new_status: AppStatus) -> Application:
        """
        Note this does NOT check whether the transition is legal — that rule
        lives in guardrails.validate_call (Week 3), because it is a policy
        decision rather than a storage concern.
        """
        rows = self._load()
        for r in rows:
            if r["app_id"] == app_id and r["owner"] == owner:
                r["status"] = new_status.value
                r["updated_at"] = _dt.datetime.now().isoformat()
                self._save(rows)
                return Application.model_validate(r)
        raise BackendError(f"no application {app_id!r}")
