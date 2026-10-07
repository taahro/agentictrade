"""Agent-to-agent capability economy primitives.

This layer sits above the existing AgenticTrade service registry and negotiation
system. It gives buyer agents a machine-readable way to decide what capability
they need, discover candidate providers, request a quote, accept a compatible
offer, and retain a transaction receipt.

Design principle:
    Agent discovers -> agent requests -> provider quotes -> buyer accepts ->
    provider delivers -> both retain a receipt.

The core is transport/payment neutral. Existing proxy, negotiation, escrow,
settlement, reputation, MCP and payment rails remain the execution layer.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True)
class CapabilityNeed:
    name: str
    description: str = ""
    category: str = ""
    tags: tuple[str, ...] = ()
    input_schema: Mapping[str, Any] = field(default_factory=dict)
    output_schema: Mapping[str, Any] = field(default_factory=dict)
    max_price: float | None = None
    currency: str = "USDC"


@dataclass(frozen=True)
class CapabilityCandidate:
    service_id: str
    provider_id: str
    name: str
    description: str = ""
    category: str = ""
    tags: tuple[str, ...] = ()
    price: float = 0.0
    currency: str = "USDC"
    reputation: float | None = None


@dataclass(frozen=True)
class CapabilityRequest:
    request_id: str
    buyer_id: str
    provider_id: str
    service_id: str
    need: CapabilityNeed
    input: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = ""


@dataclass(frozen=True)
class CapabilityOffer:
    request_id: str
    provider_id: str
    service_id: str
    price: float
    currency: str = "USDC"
    delivery: str = "sync"
    expires_at: str = ""
    terms: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CapabilityReceipt:
    receipt_id: str
    request_id: str
    buyer_id: str
    provider_id: str
    service_id: str
    status: str
    price: float
    currency: str
    issued_at: str


def discover_candidates(
    need: CapabilityNeed,
    services: list[Mapping[str, Any]],
) -> list[CapabilityCandidate]:
    """Deterministically rank marketplace services against a capability need."""
    ranked: list[tuple[float, CapabilityCandidate]] = []
    wanted_tags = {t.lower() for t in need.tags}
    wanted_text = f"{need.name} {need.description}".lower()

    for raw in services:
        tags = tuple(str(t) for t in raw.get("tags", []))
        service_tags = {t.lower() for t in tags}
        pricing = raw.get("pricing") or {}
        try:
            price = float(pricing.get("price_per_call", raw.get("price_per_call", 0)))
        except (TypeError, ValueError):
            continue
        currency = str(pricing.get("currency", raw.get("currency", need.currency)))
        if need.max_price is not None and (
            currency.upper() != need.currency.upper() or price > need.max_price
        ):
            continue

        name = str(raw.get("name", ""))
        description = str(raw.get("description", ""))
        text = f"{name} {description}".lower()
        score = 0.0
        score += 4.0 if need.name.lower() in name.lower() else 0.0
        score += 2.0 * len(wanted_tags & service_tags)
        score += 1.0 if need.category and need.category.lower() == str(raw.get("category", "")).lower() else 0.0
        score += 0.5 if any(word in text for word in wanted_text.split() if len(word) > 3) else 0.0
        if score <= 0:
            continue

        candidate = CapabilityCandidate(
            service_id=str(raw["id"]),
            provider_id=str(raw.get("provider_id", "")),
            name=name,
            description=description,
            category=str(raw.get("category", "")),
            tags=tags,
            price=price,
            currency=currency,
            reputation=raw.get("reputation"),
        )
        ranked.append((score, candidate))

    ranked.sort(key=lambda item: (-item[0], item[1].price, item[1].service_id))
    return [candidate for _, candidate in ranked]


def create_request(
    buyer_id: str,
    candidate: CapabilityCandidate,
    need: CapabilityNeed,
    input_data: Mapping[str, Any] | None = None,
    now: str | None = None,
) -> CapabilityRequest:
    if not buyer_id or buyer_id == candidate.provider_id:
        raise ValueError("buyer_provider_must_differ")
    if need.max_price is not None and candidate.price > need.max_price:
        raise ValueError("candidate_exceeds_budget")
    return CapabilityRequest(
        request_id=str(uuid.uuid4()),
        buyer_id=buyer_id,
        provider_id=candidate.provider_id,
        service_id=candidate.service_id,
        need=need,
        input=input_data or {},
        created_at=now or datetime.now(timezone.utc).isoformat(),
    )


def accept_offer(
    request: CapabilityRequest,
    offer: CapabilityOffer,
    now: str | None = None,
) -> CapabilityReceipt:
    """Validate and accept an offer; payment remains delegated to existing rails."""
    if request.request_id != offer.request_id:
        raise ValueError("request_id_mismatch")
    if request.provider_id != offer.provider_id:
        raise ValueError("provider_id_mismatch")
    if request.service_id != offer.service_id:
        raise ValueError("service_id_mismatch")
    if offer.currency.upper() != request.need.currency.upper():
        raise ValueError("currency_mismatch")
    if request.need.max_price is not None and offer.price > request.need.max_price:
        raise ValueError("offer_exceeds_buyer_limit")
    if offer.price < 0:
        raise ValueError("negative_offer")

    return CapabilityReceipt(
        receipt_id=str(uuid.uuid4()),
        request_id=request.request_id,
        buyer_id=request.buyer_id,
        provider_id=request.provider_id,
        service_id=request.service_id,
        status="accepted",
        price=offer.price,
        currency=offer.currency,
        issued_at=now or datetime.now(timezone.utc).isoformat(),
    )
