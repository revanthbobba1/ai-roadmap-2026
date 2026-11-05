"""
prompt_library.py — Month 1, Week 1
AI Roadmap 2026 | Rev Bobba

Reusable, parameterized prompt templates. The point: no hardcoded prompt
strings scattered across files. One place to define a prompt, version it,
and reuse it.

Vocabulary used below:
  - zero-shot   : instruction only, no examples
  - few-shot    : instruction + 2-3 worked examples showing the desired output
  - role prompt : a persona set in the system prompt ("You are a senior code
                  reviewer") which shifts tone and strictness
  - CoT         : chain-of-thought — instructing the model to reason step by
                  step before answering

SETUP:
  1. pip install -r requirements.txt
  2. Copy .env.example to .env and add your real API keys
  3. Run: python prompt_library.py
"""

import asyncio
from dataclasses import dataclass, field

from llm_client import call_claude, call_openai


# ── Core template class ───────────────────────────────────────────────────────

@dataclass
class PromptTemplate:
    """
    One reusable prompt.

    name        : identifier, e.g. "ticket_router_v1"
    template    : the instruction text, with {placeholders} for variables
    variables   : names that must be supplied at render time
    examples    : few-shot examples as (input, output) pairs. Empty = zero-shot.
    role        : persona for the system prompt. None = default assistant.
    cot         : if True, append a step-by-step reasoning instruction
    tuned_for   : which model this was tuned against (prompts don't always
                  transfer cleanly between models)
    """
    name: str
    template: str
    variables: list[str] = field(default_factory=list)
    examples: list[tuple[str, str]] = field(default_factory=list)
    role: str | None = None
    cot: bool = False
    tuned_for: str = "claude-haiku-4-5"

    COT_SUFFIX = "\n\nThink step by step before giving your final answer."

    def render(self, **kwargs) -> str:
        """Fill in variables and attach few-shot examples + CoT instruction."""
        missing = [v for v in self.variables if v not in kwargs]
        if missing:
            raise ValueError(f"{self.name}: missing variables {missing}")

        parts = [self.template.format(**kwargs)]

        if self.examples:
            example_block = "\n\n".join(
                f"Input: {inp}\nOutput: {out}" for inp, out in self.examples
            )
            parts.insert(0, f"Here are some examples:\n\n{example_block}\n")

        if self.cot:
            parts.append(self.COT_SUFFIX)

        return "\n".join(parts)

    def system_prompt(self) -> str:
        return self.role or "You are a helpful assistant."

    async def run(self, model: str = "claude", temperature: float = 0.0, **kwargs):
        """
        Render this template and send it to a model.

        temperature defaults to 0.0, NOT the API default of 0.7. Evaluation runs
        must be reproducible: at 0.7 every run produces a different output, so a
        score change could be a real regression or just resampling noise, and
        you cannot tell which. It also makes judge validation impossible — you
        can't check a judge against an output that no longer exists.

        Raise it deliberately when variance is the thing being studied
        (self-consistency in Week 3), never by accident.
        """
        rendered = self.render(**kwargs)
        caller = call_claude if model == "claude" else call_openai
        return await caller(rendered, system_prompt=self.system_prompt(),
                            temperature=temperature)


# ── Worked example: ticket routing, zero-shot vs. few-shot ────────────────────
# This pair is the Week 1 Day 1-2 exercise. Same task, two prompt strategies.

TICKET_ROUTER_ZERO_SHOT = PromptTemplate(
    name="ticket_router_zero_shot",
    template=(
        "Classify this support ticket into exactly one category: "
        "BILLING, TECHNICAL, ACCOUNT, or OTHER.\n"
        "Respond with only the category name.\n\n"
        "Ticket: {ticket}"
    ),
    variables=["ticket"],
)

TICKET_ROUTER_FEW_SHOT = PromptTemplate(
    name="ticket_router_few_shot",
    template=(
        "Classify this support ticket into exactly one category: "
        "BILLING, TECHNICAL, ACCOUNT, or OTHER.\n"
        "Respond with only the category name.\n\n"
        "Ticket: {ticket}"
    ),
    variables=["ticket"],
    examples=[
        ("I was charged twice for last month", "BILLING"),
        ("The app crashes when I upload a PDF", "TECHNICAL"),
        ("I can't reset my password", "ACCOUNT"),
    ],
)


# ── Hard variant: a routing policy the model cannot infer ─────────────────────
#
# The first test set couldn't discriminate — every prompt scored 20/20, because
# every ticket had a giveaway keyword. This variant encodes an ARBITRARY company
# policy. Both readings of each rule are defensible; the company picked one, and
# no amount of reasoning gets the model there:
#
#   Rule A  authentication issues (password, 2FA, SSO, login) -> ACCOUNT
#           even though they read as TECHNICAL
#   Rule B  any refund request -> OTHER for manual approval
#           even though it reads as BILLING
#   Rule C  ticket spanning two categories, or too vague -> OTHER
#
# Three templates below, identical task, differing only in HOW the policy is
# conveyed: not at all, stated in prose, or demonstrated by example.

_HARD_TASK = (
    "Classify this support ticket into exactly one category: "
    "BILLING, TECHNICAL, ACCOUNT, or OTHER.\n"
    "Respond with only the category name.\n\n"
    "Ticket: {ticket}"
)

# 1. No policy at all — the control. Should lose on convention cases.
HARD_ZERO_SHOT = PromptTemplate(
    name="hard_zero_shot",
    template=_HARD_TASK,
    variables=["ticket"],
)

# 2. Policy stated as prose rules.
HARD_ZERO_SHOT_RULES = PromptTemplate(
    name="hard_zero_shot_rules",
    template=(
        "Classify this support ticket into exactly one category: "
        "BILLING, TECHNICAL, ACCOUNT, or OTHER.\n\n"
        "Routing policy:\n"
        "- Anything about passwords, two-factor codes, SSO, or logging in "
        "goes to ACCOUNT, not TECHNICAL.\n"
        "- Any request for a refund goes to OTHER for manual approval, "
        "not BILLING.\n"
        "- If a ticket spans two categories, or is too vague to place "
        "confidently, use OTHER.\n\n"
        "Respond with only the category name.\n\n"
        "Ticket: {ticket}"
    ),
    variables=["ticket"],
)

# 2b. ABLATION of #2 — the phrases "not TECHNICAL" and "not BILLING" removed,
#     everything else byte-identical. Isolates one question: did prose win
#     because it STATED the rule, or because it NAMED the prior it was
#     overriding? Rule C is unchanged (it never named a prior).
HARD_ZERO_SHOT_RULES_ABLATED = PromptTemplate(
    name="hard_zero_shot_rules_ablated",
    template=(
        "Classify this support ticket into exactly one category: "
        "BILLING, TECHNICAL, ACCOUNT, or OTHER.\n\n"
        "Routing policy:\n"
        "- Anything about passwords, two-factor codes, SSO, or logging in "
        "goes to ACCOUNT.\n"
        "- Any request for a refund goes to OTHER for manual approval.\n"
        "- If a ticket spans two categories, or is too vague to place "
        "confidently, use OTHER.\n\n"
        "Respond with only the category name.\n\n"
        "Ticket: {ticket}"
    ),
    variables=["ticket"],
)


# 3. Same policy, demonstrated instead of stated.
#    NOTE: none of these tickets appear in ticket_routing_hard.json. Overlap
#    would be LEAKAGE — the model would have been shown the answer, and the
#    score would be inflated and meaningless.
HARD_FEW_SHOT = PromptTemplate(
    name="hard_few_shot",
    template=_HARD_TASK,
    variables=["ticket"],
    examples=[
        ("My login keeps failing right after I reset the password", "ACCOUNT"),
        ("Please issue a refund for the January invoice", "OTHER"),
        ("The export button does nothing when I click it", "TECHNICAL"),
        ("The invoice total doesn't match the plan I'm on", "BILLING"),
        ("I was charged twice and now I can't sign in either", "OTHER"),
    ],
)


# ── Role / persona prompting ──────────────────────────────────────────────────
#
# Three templates, identical task and identical user prompt. The ONLY difference
# is the `role`, which becomes the system prompt — Anthropic takes it as a
# top-level `system` field, OpenAI as a first message with role="system".
#
# code_review_neutral is the CONTROL. Without it there's no way to tell whether
# a persona changed anything, or whether the model would have done that anyway.
#
# Unlike ticket routing, the output here is prose. There is no string to compare
# against, so exact_match cannot score it — which is the point of this exercise.

_REVIEW_TASK = "Review this Python code and report any problems you find.\n\n{code}"

CODE_REVIEW_NEUTRAL = PromptTemplate(
    name="code_review_neutral",
    template=_REVIEW_TASK,
    variables=["code"],
    role=None,   # control — falls back to "You are a helpful assistant."
)

CODE_REVIEW_STRICT = PromptTemplate(
    name="code_review_strict",
    template=_REVIEW_TASK,
    variables=["code"],
    role=(
        "You are a senior staff engineer conducting a rigorous pre-merge code "
        "review. You are accountable for what ships. Be exacting and direct. "
        "Flag every defect you find, including minor ones."
    ),
)

CODE_REVIEW_FRIENDLY = PromptTemplate(
    name="code_review_friendly",
    template=_REVIEW_TASK,
    variables=["code"],
    role=(
        "You are a warm, encouraging mentor helping a junior developer grow. "
        "Lead with what they did well. Keep the tone supportive and make sure "
        "they finish the review feeling motivated rather than discouraged."
    ),
)


# CoT and self-consistency — DONE, see MATH_DIRECT / MATH_COT below and
# self_consistency.py + self_consistency_extraction.py.
#
# CoT: 13/16 -> 16/16 for 9.4x cost. All the gain came from multi-step problems;
#      it bought nothing on single-step ones. (Experiment 6)
# Self-consistency: no accuracy gain in either test, because either the model
#      was already correct, or its errors were too diffuse for a majority to
#      exist — five samples produced five distinct wrong answers and the correct
#      one never appeared. It did yield a perfect confidence signal, which is a
#      better reason to run it. (Experiments 7a, 7b)


# ── Task type 3: math word problems ───────────────────────────────────────────
#
# Chosen because it sets up Week 3. CoT and self-consistency need a task where
# reasoning can actually fail — classification is too shallow to show a gain.
#
# Test set is stratified 1step / 2step / multistep / trap. The traps are the
# classic ones (bat-and-ball, lily pad, 5 machines) where the intuitive answer
# is wrong — that's where CoT should earn its tokens, if it earns them anywhere.
#
# Answers are bare numbers so exact_match works with no new scorer.

_MATH_TASK = "{problem}"
_MATH_FORMAT = "\n\nRespond with only the final number. No units, no working, no explanation."

MATH_DIRECT = PromptTemplate(
    name="math_direct",
    template=_MATH_TASK + _MATH_FORMAT,
    variables=["problem"],
)

MATH_COT = PromptTemplate(
    name="math_cot",
    template=(
        _MATH_TASK +
        "\n\nWork through this step by step, then give your final answer on the "
        "last line in the form:\nANSWER: <number>"
    ),
    variables=["problem"],
)


# ── Task type 4: structured entity extraction ─────────────────────────────────
#
# Sets up Week 2 — Pydantic validation, retry-on-invalid, and tool calling all
# need a task whose output has a schema.
#
# Stratified clean / reordered / missing_field / distractor. The interesting
# categories are the last two: missing_field tests whether the model invents a
# value rather than emitting null (hallucination under schema pressure), and
# distractor tests whether it grabs the first number it sees.

_EXTRACT_SCHEMA = (
    "Extract the order details as JSON with exactly these keys:\n"
    "  order_id    string, digits only, no '#'\n"
    "  customer    string, the buying customer (not a sales rep)\n"
    "  date        string, ISO format YYYY-MM-DD\n"
    "  quantity    integer\n"
    "  unit_price  number, price per single unit\n\n"
    "Use null for any field not stated in the text. Do not guess.\n\n"
    "Text: {text}"
)

EXTRACT_PLAIN = PromptTemplate(
    name="extract_plain",
    template=_EXTRACT_SCHEMA,
    variables=["text"],
)

# "Return ONLY raw JSON" is here deliberately. Month 0 found both models wrap
# JSON in markdown fences regardless — a training-data habit from GitHub and
# Stack Overflow. Week 2 replaces this plea with actual schema enforcement.
EXTRACT_STRICT = PromptTemplate(
    name="extract_strict",
    template=(
        _EXTRACT_SCHEMA +
        "\n\nReturn ONLY the raw JSON object. No markdown code fences, no "
        "commentary, no preamble."
    ),
    variables=["text"],
)


# ── Prompt chaining — split the review into enumerate, then assess ────────────
#
# The single-prompt review asks for several things at once: find the problems,
# judge how serious each is, explain them, and suggest fixes. Those objectives
# compete — output budget spent explaining issue #1 is budget not spent finding
# issue #6, and the friendly persona demonstrably traded coverage for tone.
#
# The chain separates them:
#   step 1  enumerate ONLY. No severity, no explanation, no fixes.
#   step 2  take that list and assess it.
#
# Step 1 has a single objective and nothing to trade against, so it should find
# more. Step 2 gets a complete list to work from rather than generating and
# judging simultaneously.
#
# (This is the same "enumerate before triaging" habit that the interview
# scorecards flag as a recurring gap — worth knowing whether it helps a model
# for the same reason it helps a candidate.)

_SEVERITY_RUBRIC = (
    "Severity definitions:\n"
    "  critical - exploitable security hole, data loss, or corruption\n"
    "  high     - causes incorrect behaviour or a crash in normal use\n"
    "  medium   - problems under some conditions, or harms maintainability\n"
    "  trivial  - style only, no behavioural impact"
)

# CONTROL for the chaining experiment. The chained step 2 includes the severity
# rubric; code_review_strict does not. Comparing those two would confound
# chaining with the rubric — a third variable smuggled into a two-arm test.
# This arm is single-prompt WITH the rubric, so `chained` vs this one isolates
# chaining alone.
CODE_REVIEW_STRICT_RUBRIC = PromptTemplate(
    name="code_review_strict_rubric",
    template=(
        "Review this Python code and report any problems you find. "
        "For each problem, assign a severity.\n\n" + _SEVERITY_RUBRIC + "\n\n{code}"
    ),
    variables=["code"],
    role=(
        "You are a senior staff engineer conducting a rigorous pre-merge code "
        "review. You are accountable for what ships. Be exacting and direct. "
        "Flag every defect you find, including minor ones."
    ),
)

REVIEW_CHAIN_ENUMERATE = PromptTemplate(
    name="review_chain_enumerate",
    template=(
        "List every problem you can find in this Python code.\n\n"
        "Output ONLY a numbered list. One problem per line, stated in a single "
        "short phrase. Do not assign severity. Do not explain. Do not suggest "
        "fixes. Do not write any preamble or conclusion.\n\n"
        "{code}"
    ),
    variables=["code"],
)

REVIEW_CHAIN_ASSESS = PromptTemplate(
    name="review_chain_assess",
    template=(
        "Here is a Python file and a list of problems already identified in it.\n\n"
        "CODE:\n{code}\n\n"
        "PROBLEMS FOUND:\n{problems}\n\n"
        "Write the code review. For each problem, state it clearly, assign a "
        "severity, and explain the consequence. If you notice a problem missing "
        "from the list, include it too.\n\n" + _SEVERITY_RUBRIC
    ),
    variables=["code", "problems"],
)


# ── Hard extraction — nested schema with cross-field arithmetic ───────────────
#
# The flat schema had a 0% failure rate (48/48 valid across two models). This
# one adds an enum, format patterns, a nested list, and a subtotal that must
# equal the sum of the line items — so the retry loop has something to catch.

EXTRACT_HARD = PromptTemplate(
    name="extract_hard",
    template=(
        "Extract the order as JSON with exactly these keys:\n"
        "  order_id    string, digits only\n"
        "  status      one of: pending, shipped, delivered, cancelled\n"
        "  currency    ISO 4217 code, uppercase (e.g. USD, GBP, EUR)\n"
        "  items       array of objects, each with:\n"
        "                sku         string, format XX-000 (uppercase letters,\n"
        "                            hyphen, digits)\n"
        "                quantity    integer\n"
        "                unit_price  number, price for ONE unit\n"
        "  subtotal    number, must equal the sum of quantity x unit_price\n"
        "              across all items. Exclude shipping and tax.\n\n"
        "Text: {text}"
    ),
    variables=["text"],
)


# ── Registry ──────────────────────────────────────────────────────────────────
# Central lookup so the eval harness can fetch templates by name.

LIBRARY: dict[str, PromptTemplate] = {
    t.name: t for t in [
        TICKET_ROUTER_ZERO_SHOT,
        TICKET_ROUTER_FEW_SHOT,
        HARD_ZERO_SHOT,
        HARD_ZERO_SHOT_RULES,
        HARD_ZERO_SHOT_RULES_ABLATED,
        HARD_FEW_SHOT,
        CODE_REVIEW_NEUTRAL,
        CODE_REVIEW_STRICT,
        CODE_REVIEW_FRIENDLY,
        CODE_REVIEW_STRICT_RUBRIC,
        REVIEW_CHAIN_ENUMERATE,
        REVIEW_CHAIN_ASSESS,
        MATH_DIRECT,
        MATH_COT,
        EXTRACT_PLAIN,
        EXTRACT_STRICT,
        EXTRACT_HARD,
    ]
}


def get(name: str) -> PromptTemplate:
    if name not in LIBRARY:
        raise KeyError(f"Unknown template '{name}'. Have: {list(LIBRARY)}")
    return LIBRARY[name]


# ── Smoke test ────────────────────────────────────────────────────────────────

async def main():
    ticket = "My invoice shows a charge I don't recognize"

    for name in ["ticket_router_zero_shot", "ticket_router_few_shot"]:
        template = get(name)
        print(f"\n{'─'*60}\n{name}\n{'─'*60}")
        print(template.render(ticket=ticket))
        result = await template.run(model="claude", ticket=ticket)
        print(f"\n→ {result.response.strip()}")


if __name__ == "__main__":
    asyncio.run(main())
