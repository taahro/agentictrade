"""Provider-side primitives for the agent-to-agent capability economy.

Phase 3 adds the provider half of the protocol:
capability cards -> quote generation -> delivery contracts.

The module remains independent from transport, payment, and persistence. Existing
AgenticTrade registry, negotiation, x402, escrow, settlement, reputation, and
Provider Agent infrastructure remain the execution substrate.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from marketplace.agent_economy import (
    CapabilityNeed,
    CapabilityOffer,
    CapabilityReceipt,
    CapabilityRequest,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class CapabilityCard:
    """Machine-readable description of a provider capability."""

    capability_id: str
    provider_id: str
    service_id: str
    name: str
    description: str = ""
    category: str = ""
    tags: tuple[str, ...] = ()
    input_schema: Mapping[str, Any] = field(default_factory=dict)
    output_schema: Mapping[str, Any] = field(default_factory=dict)
    price: Decimal = Decimal("0")
    currency: str = "USDC"
    delivery_modes: tuple[str, ...] = ("sync",)
    sla: Mapping[str, Any] = field(default_factory=dict)
    terms: Mapping[str, Any] = field(default_factory=dict)
    version: str = "1.0"
    active: bool = True

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready machine-readable capability card."""
        return {
            "capability_id": self.capability_id,
            "provider_id": self.provider_id,
            "service_id": self.service_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "tags": list(self.tags),
            "input_schema": dict(self.input_schema),
            "output_schema": dict(self.output_schema),
            "pricing": {"price": str(self.price), "currency": self.currency},
            "delivery_modes": list(self.delivery_modes),
            "sla": dict(self.sla),
            "terms": dict(self.terms),
            "version": self.version,
            "active": self.active,
        }

    def validate(self) -> None:
        """Validate the provider's public capability contract."""
        if not self.capability_id.strip():
            raise ValueError("capability_id_required")
        if not self.provider_id.strip():
            raise ValueError("provider_id_required")
        if not self.service_id.strip():
            raise ValueError("service_id_required")
        if not self.name.strip():
            raise ValueError("capability_name_required")
        try:
            price = Decimal(str(self.price))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("capability_price_invalid") from exc
        if price < 0:
            raise ValueError("capability_price_negative")
        if not self.currency.strip():
            raise ValueError("capability_currency_required")
        if not self.delivery_modes:
            raise ValueError("delivery_mode_required")


@dataclass(frozen=True)
class ProviderQuotePolicy:
    """Deterministic provider-side rules for generating offers."""

    quote_ttl_seconds: int = 300
    max_price: Decimal | None = None
    allowed_delivery_modes: tuple[str, ...] = ("sync", "async")
    default_delivery_mode: str = "sync"

    def validate(self) -> None:
        if self.quote_ttl_seconds <= 0:
            raise ValueError("quote_ttl_must_be_positive")
        if self.default_delivery_mode not in self.allowed_delivery_modes:
            raise ValueError("default_delivery_mode_not_allowed")

    def authorize_request(
        self,
        request: CapabilityRequest,
        card: CapabilityCard,
        *,
        now: datetime | None = None,
    ) -> None:
        """Check that a card may serve a given capability request."""
        self.validate()
        card.validate()

        if not card.active:
            raise ValueError("capability_inactive")
        if request.provider_id != card.provider_id:
            raise ValueError("provider_id_mismatch")
        if request.service_id != card.service_id:
            raise ValueError("service_id_mismatch")
        if request.need.currency.upper() != card.currency.upper():
            raise ValueError("currency_mismatch")

        if request.need.max_price is not None and card.price > Decimal(str(request.need.max_price)):
            raise ValueError("provider_price_exceeds_buyer_limit")

        if self.max_price is not None and card.price > self.max_price:
            raise ValueError("capability_exceeds_provider_policy")

        if self.default_delivery_mode not in card.delivery_modes:
            raise ValueError("delivery_mode_unavailable")

        if now is not None and request.created_at:
            try:
                request_time = datetime.fromisoformat(request.created_at)
                if request_time.tzinfo is None:
                    request_time = request_time.replace(tzinfo=timezone.utc)
                if now.astimezone(timezone.utc) < request_time.astimezone(timezone.utc):
                    raise ValueError("request_time_invalid")
            except ValueError:
                raise
            except Exception as exc:
                raise ValueError("request_timestamp_invalid") from exc

    def generate_offer(
        self,
        request: CapabilityRequest,
        card: CapabilityCard,
        *,
        price: Decimal | str | float | None = None,
        delivery: str | None = None,
        terms: Mapping[str, Any] | None = None,
        now: datetime | None = None,
    ) -> CapabilityOffer:
        """Generate a machine-readable provider offer for a request."""
        now = now or _utcnow()
        self.authorize_request(request, card, now=now)

        quoted_price = Decimal(str(card.price if price is None else price))
        if quoted_price < 0:
            raise ValueError("offer_price_negative")
        if request.need.max_price is not None and quoted_price > Decimal(str(request.need.max_price)):
            raise ValueError("offer_exceeds_buyer_limit")
        if self.max_price is not None and quoted_price > self.max_price:
            raise ValueError("offer_exceeds_provider_policy")

        chosen_delivery = delivery or self.default_delivery_mode
        if chosen_delivery not in self.allowed_delivery_modes:
            raise ValueError("delivery_mode_not_allowed")
        if chosen_delivery not in card.delivery_modes:
            raise ValueError("delivery_mode_unavailable")

        expires_at = _iso(now + timedelta(seconds=self.quote_ttl_seconds))
        offer_terms = {
            "capability_id": card.capability_id,
            "capability_version": card.version,
            "input_schema": dict(card.input_schema),
            "output_schema": dict(card.output_schema),
            "sla": dict(card.sla),
            **dict(card.terms),
            **dict(terms or {}),
        }

        return CapabilityOffer(
            request_id=request.request_id,
            provider_id=card.provider_id,
            service_id=card.service_id,
            price=float(quoted_price),
            currency=card.currency,
            delivery=chosen_delivery,
            expires_at=expires_at,
            terms=offer_terms,
        )


@dataclass(frozen=True)
class CapabilityDeliveryContract:
    """Agreed delivery contract produced from an accepted offer."""

    contract_id: str
    request_id: str
    buyer_id: str
    provider_id: str
    service_id: str
    capability_id: str
    capability_version: str
    price: Decimal
    currency: str
    delivery: str
    output_schema: Mapping[str, Any] = field(default_factory=dict)
    sla: Mapping[str, Any] = field(default_factory=dict)
    terms: Mapping[str, Any] = field(default_factory=dict)
    deadline: str = ""
    status: str = "accepted"

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready delivery contract."""
        return {
            "contract_id": self.contract_id,
            "request_id": self.request_id,
            "buyer_id": self.buyer_id,
            "provider_id": self.provider_id,
            "service_id": self.service_id,
            "capability_id": self.capability_id,
            "capability_version": self.capability_version,
            "pricing": {"price": str(self.price), "currency": self.currency},
            "delivery": self.delivery,
            "output_schema": dict(self.output_schema),
            "sla": dict(self.sla),
            "terms": dict(self.terms),
            "deadline": self.deadline,
            "status": self.status,
        }

    @classmethod
    def from_acceptance(
        cls,
        request: CapabilityRequest,
        offer: CapabilityOffer,
        card: CapabilityCard,
        receipt: CapabilityReceipt,
    ) -> "CapabilityDeliveryContract":
        if receipt.request_id != request.request_id:
            raise ValueError("receipt_request_mismatch")
        if receipt.price != offer.price:
            raise ValueError("receipt_price_mismatch")
        if receipt.provider_id != offer.provider_id:
            raise ValueError("receipt_provider_mismatch")
        if receipt.service_id != offer.service_id:
            raise ValueError("receipt_service_mismatch")

        card.validate()

        return cls(
            contract_id=f"contract_{uuid.uuid4().hex[:16]}",
            request_id=request.request_id,
            buyer_id=request.buyer_id,
            provider_id=offer.provider_id,
            service_id=offer.service_id,
            capability_id=card.capability_id,
            capability_version=card.version,
            price=Decimal(str(offer.price)),
            currency=offer.currency,
            delivery=offer.delivery,
            output_schema=dict(card.output_schema),
            sla=dict(card.sla),
            terms=dict(offer.terms),
            deadline=str(offer.terms.get("delivery_deadline", "")),
            status="accepted",
        )
