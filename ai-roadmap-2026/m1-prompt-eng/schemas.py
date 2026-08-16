"""
schemas.py — Month 1, Week 2

Pydantic schemas for structured LLM output.

WHY THIS EXISTS
---------------
Experiment 3 compared extracted JSON as plain dicts. That answered "are the
values right?" but not "is this object actually usable?" — a dict with
quantity="3" (a string) compares equal enough to pass a loose check and then
blows up the first time something does arithmetic on it.

Pydantic gives three things a dict comparison can't:

  1. TYPE ENFORCEMENT     quantity must be an int, not "3"
  2. CONSTRAINTS          quantity must be > 0; unit_price >= 0
  3. A STRUCTURED ERROR   ValidationError says exactly which field failed and
                          why — which is the message the Week 2 retry loop
                          feeds back to the model

That third one is the real reason. Without a machine-readable error there's
nothing useful to re-prompt with.

STRICT VS LENIENT — the gotcha worth knowing
--------------------------------------------
Pydantic v2 COERCES by default. Given quantity="3" it will happily hand you
int 3 and report success. That's convenient in application code and dishonest
in an eval: you'd be measuring Pydantic's tolerance, not the model's output.

Both variants are defined below so the difference is measurable:
  Order        - default coercion. "Would this work in my app?"
  OrderStrict  - strict types. "Did the model actually emit correct types?"
"""

import datetime as _dt

from pydantic import BaseModel, ConfigDict, Field


class Order(BaseModel):
    """Lenient — Pydantic coerces where it reasonably can."""

    # NOTE: `datetime` is imported as `_dt` because the field is also called
    # `date`. Writing `date: date | None` shadows the imported type inside the
    # class body and fails with a confusing "unsupported operand for |" error.
    order_id: str = Field(pattern=r"^\d+$", description="digits only, no '#'")
    customer: str | None = Field(default=None, description="buyer, not sales rep")
    date: _dt.date | None = None
    quantity: int | None = Field(default=None, gt=0)
    unit_price: float | None = Field(default=None, ge=0)


class OrderStrict(Order):
    """
    Strict on types the model could plausibly get wrong; lenient where the wire
    format leaves no choice.

    Comparing pass rates between Order and OrderStrict isolates how often the
    model emitted a JSON string where the schema asked for a number. With
    coercion on, that works — until the one field Pydantic can't coerce, and
    then it fails somewhere far from the cause.

    WHY `date` IS EXEMPT: JSON has no date type. An ISO date always arrives as
    the string "2026-03-04", so a fully-strict schema rejects every valid
    input. Blanket `strict=True` looks rigorous and is simply broken here —
    it would measure the wire format, not the model.

    General rule: apply strictness per field, based on whether the wire format
    can actually represent the type you want.
    """

    model_config = ConfigDict(strict=True)

    date: _dt.date | None = Field(default=None, strict=False)


# ── Hard schema — built to actually fail ──────────────────────────────────────
#
# The flat Order schema had a 0% failure rate: 48/48 responses valid across two
# models and both strictness settings. A retry loop needs something to retry, so
# this schema adds the constraint types models genuinely get wrong:
#
#   1. ENUM             a fixed value set. Models emit near-misses —
#                       "Shipped", "shipped_out", "in transit"
#   2. PATTERN          SKU and currency formats. Models normalise inconsistently
#   3. NESTED LIST      line items. Structural depth, not just more fields
#   4. CROSS-FIELD      subtotal must equal sum(qty * price). Requires arithmetic,
#                       which is where models actually slip
#
# (4) is the highest-yield of these. Every other check tests formatting; this one
# tests whether the extracted numbers are mutually consistent — a class of error
# no per-field validator can catch.

from enum import Enum

from pydantic import ValidationInfo, field_validator, model_validator


class OrderStatus(str, Enum):
    PENDING = "pending"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class LineItem(BaseModel):
    # NOTE: float, not Decimal. Production money code should use Decimal — the
    # code-review experiment flagged exactly this — but Pydantic serialises
    # Decimal to a JSON string, which would complicate scoring without teaching
    # anything about extraction.
    sku: str = Field(pattern=r"^[A-Z]{2,4}-\d{3,5}$", description="e.g. AB-1234")
    quantity: int = Field(gt=0)
    unit_price: float = Field(ge=0)


class HardOrder(BaseModel):
    order_id: str = Field(pattern=r"^\d+$")
    status: OrderStatus
    currency: str = Field(pattern=r"^[A-Z]{3}$", description="ISO 4217")
    items: list[LineItem] = Field(min_length=1)
    subtotal: float = Field(ge=0)

    @model_validator(mode="after")
    def subtotal_matches_items(self):
        """
        Cross-field check: does the stated subtotal equal the line items?

        This is the constraint that catches real extraction errors. A model can
        get every individual field right and still produce an internally
        inconsistent object — misreading one quantity makes the arithmetic wrong
        without any single field looking invalid.

        Tolerance of 1 cent absorbs float representation noise.
        """
        computed = sum(i.quantity * i.unit_price for i in self.items)
        if abs(computed - self.subtotal) > 0.01:
            raise ValueError(
                f"subtotal {self.subtotal} does not match line items "
                f"(computed {computed:.2f})"
            )
        return self


class OrderNoSubtotal(BaseModel):
    """
    HardOrder with `subtotal` removed.

    Both models extract every line item correctly and then get the sum wrong —
    100% failure on the arithmetic cases, unchanged by tool calling. The failure
    is computation, not extraction.

    So don't delegate the computation. Have the model extract facts; derive
    totals in Python, where the answer is exact and free:

        obj      = extract(text)                                    # model
        subtotal = sum(i.quantity * i.unit_price for i in obj.items)  # code

    No cross-field validator here — with nothing derived, there is nothing to be
    inconsistent with.

    General principle: never ask a model for a value computable from values it
    already gave you.
    """

    order_id: str = Field(pattern=r"^\d+$")
    status: OrderStatus
    currency: str = Field(pattern=r"^[A-Z]{3}$", description="ISO 4217")
    items: list[LineItem] = Field(min_length=1)


# ── Tool-calling schema (Week 2 Day 3-4 uses this) ────────────────────────────

def order_json_schema() -> dict:
    """
    JSON Schema for the Order model, the format both providers' tool-calling
    APIs expect. Generated from the Pydantic model rather than hand-written, so
    the schema and the validator can't drift apart.
    """
    return Order.model_json_schema()


if __name__ == "__main__":
    import json

    print("LENIENT vs STRICT on the same input\n")
    cases = [
        ('{"order_id": "4417", "customer": "Dana Kim", "date": "2026-03-04", '
         '"quantity": 3, "unit_price": 19.99}', "correct types"),
        ('{"order_id": "4417", "customer": "Dana Kim", "date": "2026-03-04", '
         '"quantity": "3", "unit_price": "19.99"}', "numbers as strings"),
        ('{"order_id": "#4417", "customer": "Dana Kim", "date": "2026-03-04", '
         '"quantity": 3, "unit_price": 19.99}', "order_id keeps the '#'"),
        ('{"order_id": "4417", "customer": null, "date": null, '
         '"quantity": 4, "unit_price": null}', "nulls for absent fields"),
        ('{"order_id": "4417", "quantity": 0, "unit_price": 19.99}', "quantity 0"),
    ]
    for raw, label in cases:
        d = json.loads(raw)
        try:
            Order.model_validate(d)
            lenient = "pass"
        except Exception as e:
            lenient = f"FAIL ({e.error_count()} err)"
        try:
            OrderStrict.model_validate(d)
            strict = "pass"
        except Exception as e:
            strict = f"FAIL ({e.error_count()} err)"
        print(f"  {label:<24} lenient={lenient:<14} strict={strict}")
