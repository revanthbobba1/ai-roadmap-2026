"""
tools/registry.py — Month 2, Week 1

The tool registry: the list of tools you hand the model, each with a name, a
natural-language description, and a JSON Schema.

THE DESCRIPTION IS THE ROUTER
-----------------------------
There is no separate routing component. The model picks a tool by matching the
user's intent against these descriptions, inside a single forward pass. Which
means tool description design is the highest-leverage knob in agent design —
and Week 2 measures exactly that by deliberately writing overlapping
descriptions, recording the misroute rate, then rewriting them.

Worth holding on to for Month 3: when retrieval arrives, it is just another
entry in this dict. Not a parallel subsystem with a router in front — one more
tool the model may choose. That misconception cost ~3/10 on the agent routing
mock.
"""

from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel


@dataclass
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    fn: Callable          # (validated_args: BaseModel, ctx) -> str

    def schema(self) -> dict:
        """JSON Schema from the Pydantic model — generated, never hand-written,
        so the schema the model sees and the validator can't drift apart."""
        return self.args_model.model_json_schema()

    def anthropic_spec(self) -> dict:
        return {"name": self.name, "description": self.description,
                "input_schema": self.schema()}

    def openai_spec(self) -> dict:
        return {"type": "function", "function": {
            "name": self.name, "description": self.description,
            "parameters": self.schema()}}


REGISTRY: dict[str, Tool] = {}


def register(tool: Tool):
    if tool.name in REGISTRY:
        raise ValueError(f"duplicate tool {tool.name!r}")
    REGISTRY[tool.name] = tool
    return tool


def specs(provider: str = "claude") -> list[dict]:
    """All registered tools, in the provider's wire format."""
    return [t.anthropic_spec() if provider == "claude" else t.openai_spec()
            for t in REGISTRY.values()]


def get(name: str) -> Tool:
    if name not in REGISTRY:
        raise KeyError(f"unknown tool {name!r}. registered: {list(REGISTRY)}")
    return REGISTRY[name]
