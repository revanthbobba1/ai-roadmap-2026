"""
descriptions.py — Month 2, Week 2

Two sets of tool descriptions, so the effect of description design can be
measured rather than asserted.

THE EXPERIMENT
--------------
There is no routing component in an agent. The model picks a tool by matching
the user's intent against these strings, inside a single forward pass. So the
descriptions ARE the router — which makes this the highest-leverage knob in
agent design, and the one almost nobody tunes.

  OVERLAPPING   vague, interchangeable. All three sound like "find job info."
  SEPARABLE     each says what it does AND what it does not cover.

Run routing_eval.py against both and compare the misroute rate.

WHY "WHAT IT DOES NOT COVER" MATTERS
------------------------------------
A description that only states its own purpose leaves the model to infer
boundaries. Three tools that each sound reasonable for "look up a job" give it
no basis to choose. Naming the exclusion — "does not search saved jobs, use
list_applications for those" — turns three overlapping circles into a partition.

This is the same finding as Month 1's Experiment 1b: prose that specifies a
boundary beats an example that marks one point near it.
"""

from tools import registry

# ── Variant A: overlapping. Each is individually reasonable and collectively
#    useless, which is exactly how real tool sets drift as they grow.
OVERLAPPING = {
    "search_jobs":       "Find job information.",
    "get_job_details":   "Get information about a job.",
    "list_applications": "Look up job records for the user.",
}

# ── Variant B: separable. Same tools, same schemas, boundaries stated.
SEPARABLE = {
    "search_jobs": (
        "Search EXTERNAL job postings the user has not seen yet. Returns a "
        "short list: id, title, company, location, salary. Omit `query` to "
        "list everything in a location. Does NOT return full descriptions "
        "(use get_job_details) and does NOT cover jobs the user already saved "
        "(use list_applications)."
    ),
    "get_job_details": (
        "Get the FULL description of ONE job, given a job_id you already have "
        "from a previous search_jobs result. Returns requirements, "
        "responsibilities, salary. Requires a job_id — if you do not have one, "
        "call search_jobs first. Does NOT search."
    ),
    "list_applications": (
        "List jobs the user has ALREADY SAVED to their own tracker, optionally "
        "filtered by status. Use for questions about what the user has applied "
        "to or is tracking — anything phrased as 'my' or 'I'. Does NOT find "
        "new jobs (use search_jobs)."
    ),
}

# ── The uncontrolled variable ─────────────────────────────────────────────────
#
# First run: overlapping and separable BOTH scored 18/18. A ceiling, and the
# cause was a design error — only the descriptions were varied, while the tool
# NAMES stayed fully informative.
#
#     name:        list_applications
#     description: "Look up job records for the user."
#
# The model never needed the description. The name already said it. The weaker
# signal was varied and the stronger one left intact.
#
# These variants neutralise the names so description quality is actually
# isolated. The gap between neutral_overlapping and neutral_separable is the
# number the experiment was supposed to produce.
#
# Worth keeping as a finding in its own right: tool names are part of the
# router, not documentation. Most writing on tool design discusses only
# descriptions.

NEUTRAL_NAMES = {
    "search_jobs": "tool_a",
    "get_job_details": "tool_b",
    "list_applications": "tool_c",
}

VARIANTS = {
    "overlapping": (OVERLAPPING, False),
    "separable": (SEPARABLE, False),
    "neutral_overlapping": (OVERLAPPING, True),
    "neutral_separable": (SEPARABLE, True),
}

_ORIGINAL_NAMES: dict[str, str] = {}


def apply(variant: str):
    """
    Swap descriptions, and optionally neutralise names, on the live registry.

    Schemas and implementations are never touched — only what the model reads.
    """
    if variant not in VARIANTS:
        raise KeyError(f"unknown variant {variant!r}. have: {list(VARIANTS)}")
    descs, neutral = VARIANTS[variant]

    _restore_names()
    for real_name, desc in descs.items():
        registry.get(real_name).description = desc

    if neutral:
        for real_name, fake in NEUTRAL_NAMES.items():
            tool = registry.REGISTRY.pop(real_name)
            _ORIGINAL_NAMES[fake] = real_name
            tool.name = fake
            registry.REGISTRY[fake] = tool


def _restore_names():
    for fake, real in list(_ORIGINAL_NAMES.items()):
        if fake in registry.REGISTRY:
            tool = registry.REGISTRY.pop(fake)
            tool.name = real
            registry.REGISTRY[real] = tool
        del _ORIGINAL_NAMES[fake]


def real_name(name: str) -> str:
    """Map a possibly-neutralised name back, so scoring compares like with like."""
    return _ORIGINAL_NAMES.get(name, name)


def summary(variant: str) -> str:
    descs, neutral = VARIANTS[variant]
    width = max(len(d) for d in descs.values())
    return (f"{variant}: {len(descs)} tools, longest description {width} chars, "
            f"names {'NEUTRALISED (tool_a/b/c)' if neutral else 'descriptive'}")
