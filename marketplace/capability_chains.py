"""Phase 4 capability-chain orchestration for agent-to-agent commerce.

A chain is a deterministic dependency graph of capability purchases. It sits above
the existing marketplace/payment rails and can use AutonomousCapabilityBuyer for
execution without owning transport or payment logic.
"""
from __future__ import annotations

import inspect
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Awaitable, Callable, Mapping

from marketplace.agent_economy import CapabilityNeed


class CapabilityChainError(ValueError):
    """Raised when a capability chain is invalid or cannot execute safely."""


@dataclass(frozen=True)
class CapabilityChainStep:
    """One capability purchase inside a dependency graph."""

    step_id: str
    need: CapabilityNeed
    depends_on: tuple[str, ...] = ()
    input_bindings: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.step_id.strip():
            raise CapabilityChainError("step_id_required")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise CapabilityChainError("duplicate_dependency")
        for dependency in self.depends_on:
            if not dependency.strip():
                raise CapabilityChainError("dependency_id_required")
        if not self.need.currency.strip():
            raise CapabilityChainError("step_currency_required")

        for target, source in self.input_bindings.items():
            if not str(target).strip():
                raise CapabilityChainError("binding_target_required")
            if not str(source).startswith("$"):
                raise CapabilityChainError("binding_source_must_be_reference")

    def as_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "need": {
                "name": self.need.name,
                "description": self.need.description,
                "category": self.need.category,
                "tags": list(self.need.tags),
                "input_schema": dict(self.need.input_schema),
                "output_schema": dict(self.need.output_schema),
                "max_price": self.need.max_price,
                "currency": self.need.currency,
            },
            "depends_on": list(self.depends_on),
            "input_bindings": dict(self.input_bindings),
        }


@dataclass(frozen=True)
class CapabilityChainPlan:
    """Validated objective and dependency graph for one buyer agent."""

    buyer_id: str
    objective: str
    steps: tuple[CapabilityChainStep, ...]
    chain_id: str = field(default_factory=lambda: f"chain_{uuid.uuid4().hex}")
    currency: str = "USDC"
    max_total_price: Decimal | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.buyer_id.strip():
            raise CapabilityChainError("buyer_id_required")
        if not self.objective.strip():
            raise CapabilityChainError("objective_required")
        if not self.steps:
            raise CapabilityChainError("chain_steps_required")
        if not self.currency.strip():
            raise CapabilityChainError("chain_currency_required")

        ids: set[str] = set()
        for step in self.steps:
            step.validate()
            if step.step_id in ids:
                raise CapabilityChainError("duplicate_step_id")
            ids.add(step.step_id)
            if step.need.currency.upper() != self.currency.upper():
                raise CapabilityChainError("step_currency_mismatch")

        for step in self.steps:
            for dependency in step.depends_on:
                if dependency not in ids:
                    raise CapabilityChainError("unknown_dependency")
            for source in step.input_bindings.values():
                if source.startswith("$steps."):
                    parts = source.split(".")
                    if len(parts) < 3 or parts[2] != "output":
                        raise CapabilityChainError("invalid_step_reference")
                    dependency = parts[1]
                    if dependency not in step.depends_on:
                        raise CapabilityChainError("binding_requires_dependency")

        if self.max_total_price is not None:
            try:
                budget = Decimal(str(self.max_total_price))
            except (InvalidOperation, ValueError) as exc:
                raise CapabilityChainError("max_total_price_invalid") from exc
            if budget < 0:
                raise CapabilityChainError("max_total_price_negative")

            known_max = Decimal("0")
            for step in self.steps:
                if step.need.max_price is not None:
                    try:
                        known_max += Decimal(str(step.need.max_price))
                    except (InvalidOperation, ValueError) as exc:
                        raise CapabilityChainError("step_max_price_invalid") from exc
            if known_max > budget:
                raise CapabilityChainError("chain_budget_below_known_step_limits")

        self.execution_order()

    def execution_order(self) -> tuple[str, ...]:
        """Return a deterministic topological order or fail on a cycle."""
        by_id = {step.step_id: step for step in self.steps}
        visiting: set[str] = set()
        visited: set[str] = set()
        order: list[str] = []

        def visit(step_id: str) -> None:
            if step_id in visited:
                return
            if step_id in visiting:
                raise CapabilityChainError("dependency_cycle")
            visiting.add(step_id)
            for dependency in by_id[step_id].depends_on:
                visit(dependency)
            visiting.remove(step_id)
            visited.add(step_id)
            order.append(step_id)

        for step in self.steps:
            visit(step.step_id)
        return tuple(order)

    def as_dict(self) -> dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "buyer_id": self.buyer_id,
            "objective": self.objective,
            "currency": self.currency,
            "max_total_price": (
                str(self.max_total_price) if self.max_total_price is not None else None
            ),
            "steps": [step.as_dict() for step in self.steps],
            "execution_order": list(self.execution_order()),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CapabilityChainResult:
    """Auditable outcome of a chain execution."""

    chain_id: str
    buyer_id: str
    objective: str
    status: str
    completed_steps: tuple[str, ...]
    outputs: Mapping[str, Any] = field(default_factory=dict)
    step_results: Mapping[str, Any] = field(default_factory=dict)
    receipts: tuple[Any, ...] = ()
    total_spent_usdc: Decimal = Decimal("0")
    failed_step: str | None = None
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "buyer_id": self.buyer_id,
            "objective": self.objective,
            "status": self.status,
            "completed_steps": list(self.completed_steps),
            "outputs": dict(self.outputs),
            "receipts": list(self.receipts),
            "total_spent_usdc": str(self.total_spent_usdc),
            "failed_step": self.failed_step,
            "error": self.error,
        }


StepRunner = Callable[
    [CapabilityChainStep, Mapping[str, Any]],
    Any | Awaitable[Any],
]


class CapabilityChainExecutor:
    """Execute a capability chain using an injected buyer or runner.

    The executor performs no payment itself. By default it calls the supplied
    buyer's async purchase method, leaving discovery, policy, signing, x402,
    settlement, and provider execution to the existing commerce substrate.
    """

    def __init__(self, buyer: Any | None = None) -> None:
        self.buyer = buyer

    async def execute(
        self,
        plan: CapabilityChainPlan,
        initial_input: Mapping[str, Any] | None = None,
        *,
        runner: StepRunner | None = None,
    ) -> CapabilityChainResult:
        plan.validate()
        initial = dict(initial_input or {})
        outputs: dict[str, Any] = {}
        step_results: dict[str, Any] = {}
        receipts: list[Any] = []
        completed: list[str] = []
        spent = Decimal("0")

        if runner is None:
            if self.buyer is None or not hasattr(self.buyer, "purchase"):
                raise CapabilityChainError("buyer_or_runner_required")

            async def runner_impl(
                step: CapabilityChainStep, payload: Mapping[str, Any]
            ) -> Any:
                return await self.buyer.purchase(step.need, payload=payload)

            runner = runner_impl

        steps_by_id = {step.step_id: step for step in plan.steps}
        for step_id in plan.execution_order():
            step = steps_by_id[step_id]
            payload = _build_payload(step, initial, outputs)

            if plan.max_total_price is not None and step.need.max_price is not None:
                remaining = Decimal(str(plan.max_total_price)) - spent
                step_limit = Decimal(str(step.need.max_price))
                if step_limit > remaining:
                    return CapabilityChainResult(
                        chain_id=plan.chain_id,
                        buyer_id=plan.buyer_id,
                        objective=plan.objective,
                        status="budget_blocked",
                        completed_steps=tuple(completed),
                        outputs=dict(outputs),
                        step_results=dict(step_results),
                        receipts=tuple(receipts),
                        total_spent_usdc=spent,
                        failed_step=step_id,
                        error="step_max_price_exceeds_remaining_chain_budget",
                    )

            try:
                result = runner(step, payload)
                if inspect.isawaitable(result):
                    result = await result
            except Exception as exc:
                return CapabilityChainResult(
                    chain_id=plan.chain_id,
                    buyer_id=plan.buyer_id,
                    objective=plan.objective,
                    status="failed",
                    completed_steps=tuple(completed),
                    outputs=dict(outputs),
                    step_results=dict(step_results),
                    receipts=tuple(receipts),
                    total_spent_usdc=spent,
                    failed_step=step_id,
                    error=str(exc),
                )

            success = bool(getattr(result, "success", False))
            if not success:
                return CapabilityChainResult(
                    chain_id=plan.chain_id,
                    buyer_id=plan.buyer_id,
                    objective=plan.objective,
                    status="failed",
                    completed_steps=tuple(completed),
                    outputs=dict(outputs),
                    step_results=dict(step_results),
                    receipts=tuple(receipts),
                    total_spent_usdc=spent,
                    failed_step=step_id,
                    error=str(getattr(result, "error", "") or "step_failed"),
                )

            amount_raw = getattr(result, "amount_usdc", "0")
            try:
                spent += Decimal(str(amount_raw))
            except (InvalidOperation, ValueError):
                return CapabilityChainResult(
                    chain_id=plan.chain_id,
                    buyer_id=plan.buyer_id,
                    objective=plan.objective,
                    status="failed",
                    completed_steps=tuple(completed),
                    outputs=dict(outputs),
                    step_results=dict(step_results),
                    receipts=tuple(receipts),
                    total_spent_usdc=spent,
                    failed_step=step_id,
                    error="step_amount_invalid",
                )

            if plan.max_total_price is not None and spent > Decimal(str(plan.max_total_price)):
                return CapabilityChainResult(
                    chain_id=plan.chain_id,
                    buyer_id=plan.buyer_id,
                    objective=plan.objective,
                    status="budget_breached",
                    completed_steps=tuple(completed),
                    outputs=dict(outputs),
                    step_results=dict(step_results),
                    receipts=tuple(receipts),
                    total_spent_usdc=spent,
                    failed_step=step_id,
                    error="chain_total_spend_exceeded",
                )

            outputs[step_id] = getattr(result, "response", result)
            step_results[step_id] = result
            receipt = getattr(result, "receipt", None)
            if receipt is not None:
                receipts.append(receipt)
            completed.append(step_id)

        return CapabilityChainResult(
            chain_id=plan.chain_id,
            buyer_id=plan.buyer_id,
            objective=plan.objective,
            status="completed",
            completed_steps=tuple(completed),
            outputs=dict(outputs),
            step_results=dict(step_results),
            receipts=tuple(receipts),
            total_spent_usdc=spent,
        )


def _build_payload(
    step: CapabilityChainStep,
    initial: Mapping[str, Any],
    outputs: Mapping[str, Any],
) -> dict[str, Any]:
    """Materialize a step payload from explicit bindings or initial input."""
    if not step.input_bindings:
        return dict(initial)

    payload: dict[str, Any] = {}
    for target, source in step.input_bindings.items():
        payload[target] = _resolve_reference(source, initial, outputs)
    return payload


def _resolve_reference(
    reference: str,
    initial: Mapping[str, Any],
    outputs: Mapping[str, Any],
) -> Any:
    if reference == "$input":
        return dict(initial)

    if reference.startswith("$input."):
        return _walk(initial, reference[len("$input.") :].split("."))

    if reference.startswith("$steps."):
        parts = reference.split(".")
        if len(parts) < 3 or parts[2] != "output":
            raise CapabilityChainError("invalid_step_reference")
        step_id = parts[1]
        if step_id not in outputs:
            raise CapabilityChainError("step_output_unavailable")
        value = outputs[step_id]
        if len(parts) > 3:
            value = _walk(value, parts[3:])
        return value

    raise CapabilityChainError("unknown_input_reference")


def _walk(value: Any, path: list[str]) -> Any:
    current = value
    for key in path:
        if isinstance(current, Mapping):
            if key not in current:
                raise CapabilityChainError("input_reference_not_found")
            current = current[key]
        else:
            raise CapabilityChainError("input_reference_not_traversable")
    return current
