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

    async def run(self, model: str = "claude", **kwargs):
        """Render this template and send it to a model."""
        rendered = self.render(**kwargs)
        caller = call_claude if model == "claude" else call_openai
        return await caller(rendered, system_prompt=self.system_prompt())


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


# ── TODO Week 1 Day 3-4: role / persona prompting ─────────────────────────────
# Build two versions of the same code-review prompt with different `role`
# values, then run both against the same snippet and compare what each flags.
#
# CODE_REVIEW_STRICT = PromptTemplate(
#     name="code_review_strict",
#     template="Review this code:\n\n{code}",
#     variables=["code"],
#     role="You are a senior code reviewer. Be rigorous and flag every issue.",
# )
# CODE_REVIEW_FRIENDLY = PromptTemplate(... role="You are a friendly mentor ...")


# ── TODO Week 3: CoT and self-consistency ─────────────────────────────────────
# 1. Build a reasoning-task template with cot=True and compare accuracy and
#    token cost against the cot=False version.
# 2. Self-consistency: run the CoT template N times at temperature > 0 and
#    take the majority-vote answer. Compare against a single run.
#
# async def self_consistency(template, n=5, **kwargs):
#     results = await asyncio.gather(*[template.run(**kwargs) for _ in range(n)])
#     ...  # majority vote over parsed answers


# ── Registry ──────────────────────────────────────────────────────────────────
# Central lookup so the eval harness can fetch templates by name.

LIBRARY: dict[str, PromptTemplate] = {
    t.name: t for t in [
        TICKET_ROUTER_ZERO_SHOT,
        TICKET_ROUTER_FEW_SHOT,
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
