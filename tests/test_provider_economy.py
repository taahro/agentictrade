from decimal import Decimal

import pytest

from marketplace.agent_economy import CapabilityNeed, CapabilityRequest, accept_offer, create_request
from marketplace.provider_economy import (
    CapabilityCard,
    CapabilityDeliveryContract,
    ProviderQuotePolicy,
)


def card(**overrides):
    values = {
        "capability_id": "cap-market-data-v1",
        "provider_id": "data-agent",
        "service_id": "svc-market-data",
        "name": "Market Data",
        "description": "Current market data",
        "category": "finance",
        "tags": ("market", "data"),
        "input_schema": {
            "type": "object",
            "required": ["symbol"],
            "properties": {"symbol": {"type": "string"}},
        },
        "output_schema": {
            "type": "object",
            "required": ["price"],
            "properties": {"price": {"type": "number"}},
        },
        "price": Decimal("0.005"),
        "currency": "USDC",
        "delivery_modes": ("sync", "async"),
        "sla": {"max_latency_ms": 1500, "min_uptime_pct": 99.0},
        "terms": {"refund_on_timeout": True},
        "version": "1.0",
    }
    values.update(overrides)
    return CapabilityCard(**values)


def request(**overrides):
    need = CapabilityNeed(
        name="Market Data",
        description="Current market data",
        category="finance",
        tags=("market", "data"),
        max_price=0.01,
        currency="USDC",
    )
    candidate = __import__(
        "marketplace.agent_economy",
        fromlist=["CapabilityCandidate"],
    ).CapabilityCandidate(
        service_id="svc-market-data",
        provider_id="data-agent",
        name="Market Data",
        price=0.005,
        currency="USDC",
    )
    values = {
        "buyer_id": "trading-agent",
        "candidate": candidate,
        "need": need,
        "input_data": {"symbol": "AUD/JPY"},
        "now": "2026-10-06T00:00:00+00:00",
    }
    values.update(overrides)
    return create_request(**values)


def test_capability_card_validates():
    card().validate()


def test_capability_card_requires_name():
    with pytest.raises(ValueError, match="capability_name_required"):
        card(name="").validate()


def test_provider_generates_machine_readable_offer():
    req = request()
    offer = ProviderQuotePolicy(quote_ttl_seconds=120).generate_offer(
        req,
        card(),
    )

    assert offer.request_id == req.request_id
    assert offer.provider_id == "data-agent"
    assert offer.service_id == "svc-market-data"
    assert offer.price == 0.005
    assert offer.currency == "USDC"
    assert offer.delivery == "sync"
    assert offer.expires_at
    assert offer.terms["capability_id"] == "cap-market-data-v1"
    assert offer.terms["output_schema"]["required"] == ["price"]


def test_provider_rejects_offer_over_buyer_limit():
    req = request()
    with pytest.raises(ValueError, match="offer_exceeds_buyer_limit"):
        ProviderQuotePolicy().generate_offer(req, card(), price="0.02")


def test_provider_rejects_inactive_capability():
    req = request()
    with pytest.raises(ValueError, match="capability_inactive"):
        ProviderQuotePolicy().generate_offer(req, card(active=False))


def test_provider_rejects_unsupported_delivery():
    req = request()
    with pytest.raises(ValueError, match="delivery_mode_unavailable"):
        ProviderQuotePolicy().generate_offer(
            req,
            card(delivery_modes=("async",)),
            delivery="sync",
        )


def test_delivery_contract_is_created_from_accepted_offer():
    req = request()
    offer = ProviderQuotePolicy().generate_offer(req, card())
    receipt = accept_offer(req, offer, now="2026-10-06T00:00:01+00:00")

    contract = CapabilityDeliveryContract.from_acceptance(
        req,
        offer,
        card(),
        receipt,
    )

    assert contract.contract_id.startswith("contract_")
    assert contract.buyer_id == "trading-agent"
    assert contract.provider_id == "data-agent"
    assert contract.capability_id == "cap-market-data-v1"
    assert contract.capability_version == "1.0"
    assert contract.price == Decimal("0.005")
    assert contract.output_schema["required"] == ["price"]
    assert contract.sla["max_latency_ms"] == 1500
    assert contract.terms["refund_on_timeout"] is True


def test_delivery_contract_rejects_mismatched_receipt():
    req = request()
    offer = ProviderQuotePolicy().generate_offer(req, card())
    receipt = accept_offer(req, offer)
    bad = type(receipt)(
        receipt_id=receipt.receipt_id,
        request_id=receipt.request_id,
        buyer_id=receipt.buyer_id,
        provider_id="other-agent",
        service_id=receipt.service_id,
        status=receipt.status,
        price=receipt.price,
        currency=receipt.currency,
        issued_at=receipt.issued_at,
    )

    with pytest.raises(ValueError, match="receipt_provider_mismatch"):
        CapabilityDeliveryContract.from_acceptance(req, offer, card(), bad)
