from types import SimpleNamespace
from decimal import Decimal

import pytest

from marketplace.agent_economy import CapabilityNeed
from marketplace.capability_chains import (
    CapabilityChainError,
    CapabilityChainExecutor,
    CapabilityChainPlan,
    CapabilityChainStep,
)


def step(step_id, name, **kwargs):
    return CapabilityChainStep(
        step_id=step_id,
        need=CapabilityNeed(name=name, max_price=kwargs.pop("max_price", 0.005)),
        **kwargs,
    )


def test_chain_orders_dependencies_deterministically():
    plan = CapabilityChainPlan(
        buyer_id="orchestrator-agent",
        objective="assemble analysis",
        steps=(
            step("final", "Final Report", depends_on=("risk",)),
            step("market", "Market Data"),
            step("risk", "Risk Analysis", depends_on=("market",)),
        ),
    )

    assert plan.execution_order() == ("market", "risk", "final")


def test_chain_rejects_cycles_unknown_dependencies_and_implicit_bindings():
    cyc = CapabilityChainPlan(
        buyer_id="buyer",
        objective="cycle",
        steps=(
            step("a", "A", depends_on=("b",)),
            step("b", "B", depends_on=("a",)),
        ),
    )
    with pytest.raises(CapabilityChainError, match="dependency_cycle"):
        cyc.validate()

    missing = CapabilityChainPlan(
        buyer_id="buyer",
        objective="missing",
        steps=(step("a", "A", depends_on=("nope",)),),
    )
    with pytest.raises(CapabilityChainError, match="unknown_dependency"):
        missing.validate()

    implicit = CapabilityChainPlan(
        buyer_id="buyer",
        objective="implicit dependency",
        steps=(
            step("source", "Source"),
            step(
                "consumer",
                "Consumer",
                input_bindings={"data": "$steps.source.output"},
            ),
        ),
    )
    with pytest.raises(CapabilityChainError, match="binding_requires_dependency"):
        implicit.validate()


@pytest.mark.asyncio
async def test_chain_passes_previous_output_to_next_agent():
    seen = []

    plan = CapabilityChainPlan(
        buyer_id="trading-agent",
        objective="turn market data into risk analysis",
        steps=(
            step("market", "Market Data"),
            CapabilityChainStep(
                step_id="risk",
                need=CapabilityNeed(name="Risk Analysis", max_price=0.005),
                depends_on=("market",),
                input_bindings={
                    "symbol": "$input.symbol",
                    "market_data": "$steps.market.output",
                },
            ),
        ),
        max_total_price=Decimal("0.02"),
    )

    async def runner(current, payload):
        seen.append((current.step_id, dict(payload)))
        if current.step_id == "market":
            return SimpleNamespace(
                success=True,
                response={"price": 110.12, "trend": "down"},
                amount_usdc="0.004",
                receipt="r-market",
            )
        return SimpleNamespace(
            success=True,
            response={"risk": "elevated"},
            amount_usdc="0.003",
            receipt="r-risk",
        )

    result = await CapabilityChainExecutor().execute(
        plan,
        {"symbol": "AUD/JPY"},
        runner=runner,
    )

    assert result.status == "completed"
    assert result.completed_steps == ("market", "risk")
    assert result.total_spent_usdc == Decimal("0.007")
    assert seen[1][1] == {
        "symbol": "AUD/JPY",
        "market_data": {"price": 110.12, "trend": "down"},
    }
    assert result.outputs["risk"] == {"risk": "elevated"}
    assert result.receipts == ("r-market", "r-risk")


@pytest.mark.asyncio
async def test_chain_blocks_step_when_remaining_budget_is_too_small():
    calls = []

    plan = CapabilityChainPlan(
        buyer_id="buyer",
        objective="budget guarded chain",
        max_total_price=Decimal("0.004"),
        steps=(
            step("one", "One", max_price=0.002),
            step("two", "Two", max_price=0.002, depends_on=("one",)),
        ),
    )

    async def runner(current, payload):
        calls.append(current.step_id)
        return SimpleNamespace(
            success=True,
            response={current.step_id: True},
            amount_usdc="0.002",
            receipt=current.step_id,
        )

    result = await CapabilityChainExecutor().execute(plan, runner=runner)

    assert result.status == "budget_blocked"
    assert result.completed_steps == ("one",)
    assert result.failed_step == "two"
    assert calls == ["one"]
    assert result.total_spent_usdc == Decimal("0.002")


@pytest.mark.asyncio
async def test_chain_stops_on_failed_capability():
    calls = []

    plan = CapabilityChainPlan(
        buyer_id="buyer",
        objective="fail closed",
        steps=(
            step("one", "One"),
            step("two", "Two", depends_on=("one",)),
        ),
    )

    async def runner(current, payload):
        calls.append(current.step_id)
        return SimpleNamespace(
            success=current.step_id == "one",
            response={"ok": current.step_id == "one"},
            amount_usdc="0.002" if current.step_id == "one" else "0",
            receipt=None,
            error="provider_failed" if current.step_id == "two" else "",
        )

    result = await CapabilityChainExecutor().execute(plan, runner=runner)

    assert result.status == "failed"
    assert result.completed_steps == ("one",)
    assert result.failed_step == "two"
    assert result.error == "provider_failed"
    assert calls == ["one", "two"]


def test_chain_requires_consistent_currency_and_budget():
    with pytest.raises(CapabilityChainError, match="step_currency_mismatch"):
        CapabilityChainPlan(
            buyer_id="buyer",
            objective="mixed currencies",
            currency="USDC",
            steps=(
                CapabilityChainStep(
                    step_id="fx",
                    need=CapabilityNeed(name="FX", currency="EUR"),
                ),
            ),
        ).validate()

    with pytest.raises(CapabilityChainError, match="chain_budget_below_known_step_limits"):
        CapabilityChainPlan(
            buyer_id="buyer",
            objective="too expensive",
            max_total_price=Decimal("0.005"),
            steps=(
                step("a", "A", max_price=0.004),
                step("b", "B", max_price=0.004),
            ),
        ).validate()
