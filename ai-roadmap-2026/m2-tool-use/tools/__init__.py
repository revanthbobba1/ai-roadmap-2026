"""
tools/ — the tool set for the job application agent.

WHAT   Importing this package registers all seven tools as a side effect.
       `import tools` is why agent.py's registry is populated — which is also
       why it carries a `# noqa: F401` there; it looks unused and isn't.

══════════════════════════ reasoning and notes below ══════════════════════════

THE RISK SPREAD IS THE CURRICULUM
---------------------------------
  search_jobs         read-only, external      a bad call costs a fraction of a cent
  get_job_details     read-only, external
  list_applications   scoped read, YOUR data   owner comes from the session
  save_application    low-blast write          reversible; needs idempotency
  update_status       low-blast write          reversible; needs transition rules
  draft_followup      generative, no effect    produces text, touches nothing
  send_followup       HIGH BLAST               reaches a real person, cannot be undone

Guardrails only make sense when tools differ in what they can damage. This set
differs a lot, which is why it was chosen.

Week 1 built search_jobs as the worked example plus the two other reads; Week 3
added the writes, once the guardrails existed to protect them.
"""

from . import applications  # noqa: F401  — list_applications
from . import job_details   # noqa: F401  — get_job_details
from . import search        # noqa: F401  — search_jobs
from . import writes        # noqa: F401  — save, update_status, draft, send

#
# TODO Week 3 — do NOT add these before guardrails.py is built. A write tool
# with no idempotency key duplicates records on every retry, and a
# send_followup with no approval gate will eventually email someone by accident.
# from . import save               # save_application
# from . import status             # update_status
# from . import followup           # draft_followup, send_followup
