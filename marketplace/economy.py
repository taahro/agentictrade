"""Phase 5 agent-economy primitives.

This module adds deterministic economic behavior above the capability and chain
layers: outcome scoring, bounded dynamic pricing, referrals, composite capability
publication, and an accounting ledger.

It intentionally does not move money or replace settlement. The ledger records
economic attribution; AgenticTrade payment/settlement rails remain authoritative
for actual funds movement.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decimal(value: Decimal | str | float | int, error: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(error) from exc
    if not result.is_finite():
        raise ValueError(error)
    return result


@dataclass(frozen=True)
class CapabilityOutcome:
    """Observed result of one capability delivery."""

    capability_id: str
    provider_id: str
    buyer_id: str
    success: bool
    quality_score: Decimal = Decimal("0")
    value_score: Decimal = Decimal("0")
    latency_ms: int = 0
    price: Decimal = Decimal("0")
    currency: str = "USDC"
    verified: bool = False
    created_at: str = field(default_factory=_utcnow)

    def validate(self) -> None:
        if not self.capability_id.strip():
            raise ValueError("capability_id_required")
        if not self.provider_id.strip():
            raise ValueError("provider_id_required")
        if not self.buyer_id.strip():
            raise ValueError("buyer_id_required")
        if self.latency_ms < 0:
            raise ValueError("latency_negative")
        price = _decimal(self.price, "outcome_price_invalid")
        if price < 0:
            raise ValueError("outcome_price_negative")
        for field_name, value in (
            ("quality_score", self.quality_score),
            ("value_score", self.value_score),
        ):
            score = _decimal(value, f"{field_name}_invalid")
            if not Decimal("0") <= score <= Decimal("10"):
                raise ValueError(f"{field_name}_out_of_range")
        if not self.currency.strip():
            raise ValueError("outcome_currency_required")


@dataclass(frozen=True)
class OutcomeReputationPolicy:
    """Convert observed outcomes into a bounded capability reputation score."""

    quality_weight: Decimal = Decimal("0.45")
    reliability_weight: Decimal = Decimal("0.30")
    value_weight: Decimal = Decimal("0.15")
    latency_weight: Decimal = Decimal("0.10")
    latency_ceiling_ms: int = 5000

    def validate(self) -> None:
        weights = (
            self.quality_weight,
            self.reliability_weight,
            self.value_weight,
            self.latency_weight,
        )
        if any(_decimal(w, "reputation_weight_invalid") < 0 for w in weights):
            raise ValueError("reputation_weight_negative")
        if sum((_decimal(w, "reputation_weight_invalid") for w in weights), Decimal()) != Decimal("1"):
            raise ValueError("reputation_weights_must_sum_to_one")
        if self.latency_ceiling_ms <= 0:
            raise ValueError("latency_ceiling_invalid")

    def score(self, outcome: CapabilityOutcome) -> Decimal:
        self.validate()
        outcome.validate()
        latency_score = Decimal("10") * (
            Decimal("1")
            - min(Decimal("1"), Decimal(outcome.latency_ms) / Decimal(self.latency_ceiling_ms))
        )
        reliability_score = Decimal("10") if outcome.success else Decimal("0")
        verified_value = outcome.value_score if outcome.verified else Decimal("0")
        raw = (
            _decimal(outcome.quality_score, "quality_invalid") * self.quality_weight
            + reliability_score * self.reliability_weight
            + verified_value * self.value_weight
            + latency_score * self.latency_weight
        )
        return raw.quantize(Decimal("0.01"))


@dataclass(frozen=True)
class DynamicPricingPolicy:
    """Bounded deterministic price adjustment based on utilization and reputation."""

    base_price: Decimal
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    utilization_weight: Decimal = Decimal("0.50")
    reputation_weight: Decimal = Decimal("0.25")
    demand_weight: Decimal = Decimal("0.25")
    minimum_factor: Decimal = Decimal("0.50")
    maximum_factor: Decimal = Decimal("2.00")

    def validate(self) -> None:
        base = _decimal(self.base_price, "base_price_invalid")
        if base < 0:
            raise ValueError("base_price_negative")
        low = base if self.min_price is None else _decimal(self.min_price, "min_price_invalid")
        high = base if self.max_price is None else _decimal(self.max_price, "max_price_invalid")
        if low < 0 or high < 0 or low > high:
            raise ValueError("price_bounds_invalid")
        if self.minimum_factor <= 0 or self.maximum_factor < self.minimum_factor:
            raise ValueError("price_factor_bounds_invalid")
        weights = (self.utilization_weight, self.reputation_weight, self.demand_weight)
        if any(_decimal(w, "pricing_weight_invalid") < 0 for w in weights):
            raise ValueError("pricing_weight_negative")
        if sum((_decimal(w, "pricing_weight_invalid") for w in weights), Decimal()) != Decimal("1"):
            raise ValueError("pricing_weights_must_sum_to_one")

    def quote(
        self,
        *,
        utilization: Decimal | float | int = 0,
        reputation: Decimal | float | int = 5,
        demand: Decimal | float | int = 0,
    ) -> Decimal:
        """Return a bounded price. Inputs are normalized to a 0..10 scale."""
        self.validate()
        values = {
            "utilization": _decimal(utilization, "utilization_invalid"),
            "reputation": _decimal(reputation, "reputation_invalid"),
            "demand": _decimal(demand, "demand_invalid"),
        }
        if any(v < 0 or v > 10 for v in values.values()):
            raise ValueError("pricing_signal_out_of_range")
        utility_signal = (
            values["utilization"] * self.utilization_weight
            + values["reputation"] * self.reputation_weight
            + values["demand"] * self.demand_weight
        )
        factor = (
            self.minimum_factor
            + (self.maximum_factor - self.minimum_factor) * (utility_signal / Decimal("10"))
        )
        price = _decimal(self.base_price, "base_price_invalid") * factor
        if self.min_price is not None:
            price = max(price, _decimal(self.min_price, "min_price_invalid"))
        if self.max_price is not None:
            price = min(price, _decimal(self.max_price, "max_price_invalid"))
        return price.quantize(Decimal("0.000001"))


@dataclass(frozen=True)
class ReferralPolicy:
    """Deterministic referral reward policy."""

    reward_rate: Decimal = Decimal("0.02")
    max_reward: Decimal | None = None

    def validate(self) -> None:
        rate = _decimal(self.reward_rate, "referral_rate_invalid")
        if rate < 0 or rate > 1:
            raise ValueError("referral_rate_out_of_range")
        if self.max_reward is not None and _decimal(self.max_reward, "referral_max_invalid") < 0:
            raise ValueError("referral_max_negative")

    def reward(self, transaction_amount: Decimal | str | float) -> Decimal:
        self.validate()
        amount = _decimal(transaction_amount, "transaction_amount_invalid")
        if amount < 0:
            raise ValueError("transaction_amount_negative")
        reward = amount * _decimal(self.reward_rate, "referral_rate_invalid")
        if self.max_reward is not None:
            reward = min(reward, _decimal(self.max_reward, "referral_max_invalid"))
        return reward.quantize(Decimal("0.000001"))


@dataclass(frozen=True)
class CompositeCapability:
    """Higher-level capability created by composing purchased capabilities."""

    capability_id: str
    provider_id: str
    service_id: str
    name: str
    component_capability_ids: tuple[str, ...]
    price: Decimal
    currency: str = "USDC"
    input_schema: Mapping[str, Any] = field(default_factory=dict)
    output_schema: Mapping[str, Any] = field(default_factory=dict)
    version: str = "1.0"
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.capability_id.strip() or not self.provider_id.strip() or not self.service_id.strip():
            raise ValueError("composite_identity_required")
        if not self.name.strip():
            raise ValueError("composite_name_required")
        if not self.component_capability_ids:
            raise ValueError("composite_components_required")
        if len(set(self.component_capability_ids)) != len(self.component_capability_ids):
            raise ValueError("duplicate_composite_component")
        if _decimal(self.price, "composite_price_invalid") < 0:
            raise ValueError("composite_price_negative")
        if not self.currency.strip():
            raise ValueError("composite_currency_required")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "capability_id": self.capability_id,
            "provider_id": self.provider_id,
            "service_id": self.service_id,
            "name": self.name,
            "component_capability_ids": list(self.component_capability_ids),
            "pricing": {"price": str(self.price), "currency": self.currency},
            "input_schema": dict(self.input_schema),
            "output_schema": dict(self.output_schema),
            "version": self.version,
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True)
class EconomyEntry:
    """Accounting attribution; not a direct funds transfer."""

    entry_id: str = field(default_factory=lambda: f"econ_{uuid.uuid4().hex}")
    transaction_id: str = ""
    agent_id: str = ""
    counterparty_id: str = ""
    direction: str = "debit"  # debit | credit
    amount: Decimal = Decimal("0")
    currency: str = "USDC"
    entry_type: str = "capability_purchase"
    reference_id: str = ""
    created_at: str = field(default_factory=_utcnow)

    def validate(self) -> None:
        if not self.transaction_id or not self.agent_id:
            raise ValueError("accounting_identity_required")
        if self.direction not in {"debit", "credit"}:
            raise ValueError("accounting_direction_invalid")
        if _decimal(self.amount, "accounting_amount_invalid") < 0:
            raise ValueError("accounting_amount_negative")
        if not self.currency.strip():
            raise ValueError("accounting_currency_required")


class EconomyLedger:
    """Small deterministic accounting projection over agent-to-agent activity."""

    def __init__(self) -> None:
        self._entries: list[EconomyEntry] = []

    def record_purchase(
        self,
        *,
        buyer_id: str,
        provider_id: str,
        amount: Decimal | str | float,
        currency: str = "USDC",
        transaction_id: str | None = None,
        reference_id: str = "",
        referral_id: str | None = None,
        referral_policy: ReferralPolicy | None = None,
        platform_id: str = "agentictrade",
        platform_fee: Decimal | str | float = Decimal("0"),
    ) -> tuple[EconomyEntry, ...]:
        tx = transaction_id or f"tx_{uuid.uuid4().hex}"
        value = _decimal(amount, "purchase_amount_invalid")
        fee = _decimal(platform_fee, "platform_fee_invalid")
        if value < 0 or fee < 0 or fee > value:
            raise ValueError("purchase_amount_invalid")

        entries = [
            EconomyEntry(
                transaction_id=tx,
                agent_id=buyer_id,
                counterparty_id=provider_id,
                direction="debit",
                amount=value,
                currency=currency,
                entry_type="capability_purchase",
                reference_id=reference_id,
            ),
            EconomyEntry(
                transaction_id=tx,
                agent_id=provider_id,
                counterparty_id=buyer_id,
                direction="credit",
                amount=value - fee,
                currency=currency,
                entry_type="capability_revenue",
                reference_id=reference_id,
            ),
        ]
        if fee > 0:
            entries.append(
                EconomyEntry(
                    transaction_id=tx,
                    agent_id=platform_id,
                    counterparty_id=provider_id,
                    direction="credit",
                    amount=fee,
                    currency=currency,
                    entry_type="platform_fee",
                    reference_id=reference_id,
                )
            )

        if referral_id and referral_policy is not None:
            reward = referral_policy.reward(value)
            if reward > 0:
                if reward > (value - fee):
                    raise ValueError("referral_reward_exceeds_provider_revenue")
                entries.append(
                    EconomyEntry(
                        transaction_id=tx,
                        agent_id=referral_id,
                        counterparty_id=provider_id,
                        direction="credit",
                        amount=reward,
                        currency=currency,
                        entry_type="referral_reward",
                        reference_id=reference_id,
                    )
                )

        for entry in entries:
            entry.validate()
        self._entries.extend(entries)
        return tuple(entries)

    def entries(
        self,
        *,
        agent_id: str | None = None,
        transaction_id: str | None = None,
    ) -> tuple[EconomyEntry, ...]:
        values = self._entries
        if agent_id is not None:
            values = [e for e in values if e.agent_id == agent_id]
        if transaction_id is not None:
            values = [e for e in values if e.transaction_id == transaction_id]
        return tuple(values)

    def balance(self, agent_id: str, currency: str = "USDC") -> Decimal:
        """Return the ledger's accounting projection for one agent."""
        total = Decimal("0")
        for entry in self._entries:
            if entry.agent_id == agent_id and entry.currency.upper() == currency.upper():
                total += entry.amount if entry.direction == "credit" else -entry.amount
        return total
